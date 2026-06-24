import asyncio
import logging
from datetime import datetime
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global Mode: SET TO TRUE TO PREVENT REAL TRADING
ALERT_ONLY_MODE = True 

async def main_cycle(symbol: str, timeframe: str, db: Session):
    """
    The complete loop that runs on every candle close.
    """
    logger.info(f"--- Starting Cycle for {symbol} [{timeframe}] ---")
    
    try:
        # 1. Data & Features
        poller = MarketDataPoller(db)
        await poller.poll_symbol(symbol, timeframe)
        
        from database.schemas import MarketBar
        bars = db.query(MarketBar).filter(MarketBar.symbol == symbol, MarketBar.timeframe == timeframe).order_by(MarketBar.open_time.desc()).limit(500).all()
        import pandas as pd
        df = pd.DataFrame([{'open': b.open, 'high': b.high, 'low': b.low, 'close': b.close, 'volume': b.volume, 'open_time': b.open_time} for b in bars]).sort_values('open_time')
        
        builder = FeatureBuilder(db)
        features = await builder.build_features(symbol, timeframe, df)
        
        # 2. News & Sentiment
        scorer = EventScorer(db)
        await scorer.update_sentiment_store(symbol)
        from database.schemas import SentimentScore
        sentiment = db.query(SentimentScore).filter(SentimentScore.symbol == symbol).order_by(SentimentScore.timestamp.desc()).first()
        
        # 3. AI Decision
        aggregator = SignalAggregator()
        res = aggregator.aggregate(features, sentiment)
        
        # 4. Risk Management
        risk_eng = RiskEngine()
        levels = risk_eng.calculate_levels(symbol, res['direction'], df.iloc[-1]['close'], features)
        filters = RiskFilters()
        
        signal_data = {**res, **levels}
        approved, reason = filters.validate_trade(signal_data, sentiment, 0) # 0 = mock open trades
        
        # 5. Execution or Alert
        bot = TelegramBot()
        
        if approved and res['decision'] == "EXECUTE":
            msg = f"🚀 *TRADE EXECUTION*\nSymbol: {symbol}\nDir: {res['direction']}\nConf: {res['final_score']:.2f}%\nSL: {levels['stop_loss']:.5f}\nTP: {levels['take_profit_1']:.5f}"
            
            if ALERT_ONLY_MODE:
                logger.info(f"[ALERT ONLY] Would have executed: {res['direction']} {symbol}")
                bot.send_message(f"⚠️ *ALERT ONLY MODE*\n{msg}")
            else:
                executor = OrderExecutor()
                from src.risk_layer.position_sizer import PositionSizer
                sizer = PositionSizer()
                lot = sizer.calculate_lot_size(10000.0, 0.01, levels['risk_pips'], symbol)
                
                exec_res = executor.execute_trade(symbol, res['direction'], lot, levels['stop_loss'], levels['take_profit_1'])
                if exec_res['status'] == "success":
                    bot.send_message(f"✅ *TRADE OPENED*\n{msg}\nLot: {lot}")
        
        elif res['decision'] == "ALERT":
            bot.send_message(f"🔔 *SIGNAL ALERT*\nSymbol: {symbol}\nDir: {res['direction']}\nConf: {res['final_score']:.2f}%\nReason: {res['reasons']}")

    except Exception as e:
        logger.exception(f"Error in main cycle for {symbol}: {e}")

async def run_system():
    """
    Main loop that schedules tasks.
    """
    db = SessionLocal()
    logger.info("AI Trading System Started. Monitoring symbols...")
    
    while True:
        for symbol in settings.MONITORED_SYMBOLS:
            await main_cycle(symbol, settings.DEFAULT_TIMEFRAME, db)
            await asyncio.sleep(1) # Prevent API rate limit
        
        logger.info("Cycle complete. Sleeping until next candle (approx 1 hour)...")
        await asyncio.sleep(3600) # Sleep for 1 hour for H1 timeframe

if __name__ == "__main__":
    asyncio.run(run_system())
