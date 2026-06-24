import pandas as pd
import logging
from sqlalchemy.orm import Session
from src.feature_layer.technical_indicators import TechnicalIndicators
from src.feature_layer.price_context import PriceContext
from src.feature_layer.session_detector import SessionDetector
from src.feature_layer.multi_timeframe import MultiTimeframeAnalyzer
from database.schemas import TechnicalFeature, MarketBar
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FeatureBuilder:
    """
    Orchestrates the computation of all features and saves them to the database.
    FIX: Converted from async to sync — called by sync tasks.py and start_system.py.
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def build_features(self, symbol: str, timeframe: str, bars_df: pd.DataFrame = None):
        """
        Full pipeline: load bars -> Indicators -> Context -> Session -> Multi-TF -> DB.
        bars_df is optional: if not provided, fetches from DB automatically.
        """
        logger.info('Building features for %s [%s]...', symbol, timeframe)

        # --- Load bars if not provided ---
        if bars_df is None or bars_df.empty:
            bars = (
                self.db.query(MarketBar)
                .filter(MarketBar.symbol == symbol, MarketBar.timeframe == timeframe)
                .order_by(MarketBar.open_time.desc())
                .limit(500)
                .all()
            )
            if len(bars) < 50:
                logger.warning('Not enough bars for %s: %d', symbol, len(bars))
                return None
            bars_df = pd.DataFrame([
                {'open': float(b.open), 'high': float(b.high),
                 'low': float(b.low),   'close': float(b.close),
                 'volume': float(b.volume), 'open_time': b.open_time}
                for b in bars
            ]).sort_values('open_time').reset_index(drop=True)

        if len(bars_df) < 50:
            logger.warning('DataFrame too short for %s: %d rows', symbol, len(bars_df))
            return None

        # 1. Technical Indicators
        df = TechnicalIndicators.compute_all(bars_df)

        # 2. Price Context
        df['regime']         = PriceContext.detect_regime(df)
        df['momentum_score'] = PriceContext.get_price_relative_to_ema(df)

        # 3. Session Detection
        if 'open_time' not in df.columns:
            df = df.reset_index().rename(columns={'index': 'open_time'})
        df = SessionDetector.add_session_features(df)

        # 4. Multi-Timeframe Bias
        bias = MultiTimeframeAnalyzer.get_higher_tf_bias(symbol, timeframe)

        # 5. Build and upsert the latest bar record
        latest = df.iloc[-1]

        # Guard: open_time must not be NaT/None
        bar_time = latest.get('open_time')
        if bar_time is None or pd.isna(bar_time):
            logger.error('bar_time is null for %s — cannot save features', symbol)
            return None

        feature_record = TechnicalFeature(
            symbol         = symbol,
            timeframe      = timeframe,
            bar_time       = bar_time,
            ema_20         = float(latest.get('ema_20')  or 0),
            ema_50         = float(latest.get('ema_50')  or 0),
            ema_200        = float(latest.get('ema_200') or 0),
            rsi_14         = float(latest.get('rsi_14')  or 50),
            macd_line      = float(latest.get('macd_line')      or 0),
            macd_signal    = float(latest.get('macd_signal')    or 0),
            macd_histogram = float(latest.get('macd_histogram') or 0),
            atr_14         = float(latest.get('atr_14') or 0),
            adx_14         = float(latest.get('adx_14') or 0),
            trend_state    = str(latest.get('regime', 'UNKNOWN')),
            momentum_score = float(latest.get('momentum_score') or 0),
            regime         = f"{latest.get('session', 'UNKNOWN')}_{bias}",
            volatility_score = (
                float(latest.get('atr_14', 0)) / float(latest.get('close', 1)) * 10_000
                if latest.get('close') else 0
            ),
        )

        self.db.merge(feature_record)
        self.db.commit()
        logger.info('Features stored for %s at %s', symbol, bar_time)
        return feature_record
