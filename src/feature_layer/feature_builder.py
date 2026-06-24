import pandas as pd
import logging
from sqlalchemy.orm import Session
from src.feature_layer.technical_indicators import TechnicalIndicators
from src.feature_layer.price_context import PriceContext
from src.feature_layer.session_detector import SessionDetector
from src.feature_layer.multi_timeframe import MultiTimeframeAnalyzer
from database.schemas import TechnicalFeature
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FeatureBuilder:
    """
    Orchestrates the computation of all features and saves them to the database.
    """
    def __init__(self, db_session: Session):
        self.db = db_session

    async def build_features(self, symbol: str, timeframe: str, bars_df: pd.DataFrame):
        """
        Full pipeline: Indicators -> Context -> Session -> Multi-TF -> DB.
        """
        logger.info(f"Building features for {symbol} [{timeframe}]...")

        # 1. Technical Indicators
        df = TechnicalIndicators.compute_all(bars_df)

        # 2. Price Context
        df['regime'] = PriceContext.detect_regime(df)
        df['momentum_score'] = PriceContext.get_price_relative_to_ema(df)

        # 3. Session Detection
        # Ensure open_time is in the df for session detection
        if 'open_time' not in df.columns:
            # If it's the index, reset it
            df = df.reset_index().rename(columns={'index': 'open_time'})
        
        df = SessionDetector.add_session_features(df)

        # 4. Multi-Timeframe Bias (scalar value for the latest bar)
        bias = MultiTimeframeAnalyzer.get_higher_tf_bias(symbol, timeframe)
        
        # 5. Save the latest bar features to DB
        latest_bar = df.iloc[-1]
        
        feature_record = TechnicalFeature(
            symbol=symbol,
            timeframe=timeframe,
            bar_time=latest_bar['open_time'],
            ema_20=float(latest_bar.get('ema_20', 0)),
            ema_50=float(latest_bar.get('ema_50', 0)),
            ema_200=float(latest_bar.get('ema_200', 0)),
            rsi_14=float(latest_bar.get('rsi_14', 0)),
            macd_line=float(latest_bar.get('macd_line', 0)),
            macd_signal=float(latest_bar.get('macd_signal', 0)),
            macd_histogram=float(latest_bar.get('macd_histogram', 0)),
            atr_14=float(latest_bar.get('atr_14', 0)),
            adx_14=float(latest_bar.get('adx_14', 0)),
            trend_state=latest_bar.get('regime', 'UNKNOWN'),
            momentum_score=float(latest_bar.get('momentum_score', 0)),
            regime=f"{latest_bar.get('session', 'UNKNOWN')}_{bias}",
            # volatility_score can be normalized ATR
            volatility_score=float(latest_bar.get('atr_14', 0) / latest_bar['close'] * 10000) 
        )
        
        self.db.merge(feature_record)
        self.db.commit()
        
        logger.info(f"Features stored for {symbol} at {latest_bar['open_time']}")
        return feature_record
