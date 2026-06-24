import asyncio
import logging
from datetime import datetime, timezone
from config.settings import settings
from src.data_layer.market_data_poller import MarketDataPoller
from src.feature_layer.feature_builder import FeatureBuilder
from src.news_layer.event_scorer import EventScorer
from src.ai_layer.signal_aggregator import SignalAggregator
from src.risk_layer.risk_engine import RiskEngine
from src.risk_layer.risk_filters import RiskFilters
from src.execution_layer.order_executor import OrderExecutor
from src.monitoring_layer.telegram_bot import TelegramBot
from sqlalchemy.orm import Session
from api.main import SessionLocal
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s'
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Set to True during testing to suppress live trades
# ─────────────────────────────────────────────
ALERT_ONLY_MODE = True


async def main_cycle(symbol: str, timeframe: str, db: Session):
    """
    Full analysis pipeline for one symbol on one candle close.
    """
    logger.info('─── Cycle start: %s [%s] ───', symbol, timeframe)
    try:
        # ── 1. Poll market data from MT5 ──────────────────────────
        poller = MarketDataPoller(db)
        await poller.poll_symbol(symbol, timeframe)

        from database.schemas import MarketBar, SentimentScore
        bars = (
            db.query(MarketBar)
            .filter(MarketBar.symbol == symbol, MarketBar.timeframe == timeframe)
            .order_by(MarketBar.open_time.desc())
            .limit(500)
            .all()
        )
        if len(bars) < 50:
            logger.warning('Not enough bars for %s (%d). Skipping.', symbol, len(bars))
            return

        df = pd.DataFrame([
            {'open': b.open, 'high': b.high, 'low': b.low,
             'close': b.close, 'volume': b.volume, 'open_time': b.open_time}
            for b in bars
        ]).sort_values('open_time').reset_index(drop=True)

        # ── 2. Compute technical features ────────────────────────
        builder  = FeatureBuilder(db)
        # FIX: FeatureBuilder.build_features is synchronous — do NOT await it
        features = builder.build_features(symbol, timeframe)
        if features is None:
            logger.warning('Feature build failed for %s. Skipping.', symbol)
            return

        # ── 3. News & Sentiment ───────────────────────────────────
        scorer = EventScorer(db)
        await scorer.update_sentiment_store(symbol)
        sentiment = (
            db.query(SentimentScore)
            .filter(SentimentScore.symbol == symbol)
            .order_by(SentimentScore.timestamp.desc())
            .first()
        )
        if sentiment is None:
            from database.schemas import SentimentScore as SS
            sentiment = SS(symbol=symbol, combined_sentiment=0.0,
                           event_risk_score=0.0,
                           base_currency_sentiment=0.0,
                           quote_currency_sentiment=0.0)

        # ── 4. AI Signal Aggregation ─────────────────────────────
        aggregator = SignalAggregator()
        res        = aggregator.aggregate(features, sentiment)
        logger.info('Signal for %s: %s %s (score=%.1f)',
                    symbol, res["decision"], res["direction"], res["final_score"])

        # ── 5. Risk Levels ────────────────────────────────────────
        risk_eng = RiskEngine()
        current_price = float(df.iloc[-1]['close'])
        levels   = risk_eng.calculate_levels(symbol, res['direction'], current_price, features)

        # ── 6. Risk Filter Validation ─────────────────────────────
        filters     = RiskFilters()
        signal_data = {**res, **levels, 'symbol': symbol}
        # FIX: pass empty list [] not int 0; live balance from MT5 if available
        balance = 10_000.0
        try:
            from src.data_layer.mt5_connector import mt5_connector
            acc = mt5_connector.get_account_info()
            if acc: balance = acc.get('balance', 10_000.0)
        except Exception:
            pass
        approved, reason = filters.validate_trade(signal_data, sentiment, [], balance)

        # ── 7. Execute or Alert ───────────────────────────────────
        bot = TelegramBot()
        msg = (
            f'Symbol: {symbol}\n'
            f'Direction: {res["direction"]}\n'
            f'Confidence: {res["final_score"]:.1f}%\n'
            f'Entry: {levels["entry"]}\n'
            f'SL: {levels["stop_loss"]} ({levels["risk_pips"]} pips)\n'
            f'TP1: {levels["take_profit_1"]}  TP2: {levels["take_profit_2"]}\n'
            f'R:R: {levels["risk_reward"]}'
        )

        if approved and res['decision'] == 'EXECUTE':
            if ALERT_ONLY_MODE:
                logger.info('[ALERT ONLY] Would execute: %s %s', res["direction"], symbol)
                # FIX: pass text as keyword argument
                bot.send_message(text=f'⚠️ *ALERT ONLY MODE*\n🚀 *TRADE SIGNAL*\n{msg}')
            else:
                from src.risk_layer.position_sizer import PositionSizer
                lot      = PositionSizer().calculate_lot_size(balance, 0.01, levels['risk_pips'], symbol)
                executor = OrderExecutor()
                exec_res = executor.execute_trade(symbol, res['direction'], lot, levels['stop_loss'], levels['take_profit_1'])
                if exec_res['status'] == 'success':
                    bot.send_message(text=f'✅ *TRADE OPENED*\n{msg}\nLot: {lot}')
                else:
                    bot.send_message(text=f'❌ *ORDER FAILED*\n{exec_res.get("reason")}')

        elif res['decision'] == 'ALERT':
            bot.send_message(text=f'🔔 *SIGNAL ALERT*\n{msg}\nReasons: {res["reasons"]}')

        elif not approved:
            logger.info('Trade blocked for %s: %s', symbol, reason)

    except Exception as e:
        logger.exception('Error in cycle for %s: %s', symbol, e)


async def wait_for_next_candle(timeframe: str):
    """
    Sleeps until the close of the current candle.
    Supports H1 (3600s) and M15 (900s).
    """
    tf_seconds = {
        'M1': 60, 'M5': 300, 'M15': 900, 'M30': 1800,
        'H1': 3600, 'H4': 14400, 'D1': 86400,
    }
    interval = tf_seconds.get(timeframe.upper(), 3600)
    now      = datetime.now(timezone.utc).timestamp()
    # Time until the next candle boundary
    sleep_s  = interval - (now % interval) + 2   # +2s buffer for data to arrive
    logger.info('Next candle in %.0fs (timeframe=%s)', sleep_s, timeframe)
    await asyncio.sleep(sleep_s)


async def run_system():
    db = SessionLocal()
    logger.info('═══ AI Trading System Started ═══')
    logger.info('Symbols  : %s', settings.MONITORED_SYMBOLS)
    logger.info('Timeframe: %s', settings.DEFAULT_TIMEFRAME)
    logger.info('Mode     : %s', 'ALERT ONLY' if ALERT_ONLY_MODE else '⚠️  LIVE TRADING')

    while True:
        for symbol in settings.MONITORED_SYMBOLS:
            await main_cycle(symbol, settings.DEFAULT_TIMEFRAME, db)
            await asyncio.sleep(1)   # Prevent MT5 rate-limit
        # Wait until the next candle closes before running again
        await wait_for_next_candle(settings.DEFAULT_TIMEFRAME)


if __name__ == '__main__':
    asyncio.run(run_system())
