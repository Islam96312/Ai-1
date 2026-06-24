import pandas as pd
import numpy as np
from typing import Dict

class PriceContext:
    """
    Analyzes price action to determine market regime and key levels.
    """
    @staticmethod
    def detect_regime(df: pd.DataFrame) -> pd.Series:
        """
        Determines if the market is Trending, Ranging, or in a Breakout.
        Logic: 
        - ADX > 25: Trending
        - ADX < 20: Ranging
        - Price crossing EMA 200 + ADX rising: Potential Breakout
        """
        regimes = []
        for i in range(len(df)):
            adx = df['adx_14'].iloc[i] if 'adx_14' in df.columns else 20
            
            if adx > 25:
                regimes.append("TRENDING")
            elif adx < 20:
                regimes.append("RANGING")
            else:
                regimes.append("NEUTRAL")
        
        return pd.Series(regimes, index=df.index)

    @staticmethod
    def detect_support_resistance(df: pd.DataFrame, window=20) -> Dict[str, float]:
        """
        Simple Support/Resistance detection based on local swing highs/lows.
        """
        recent_df = df.tail(window)
        return {
            "support": recent_df['low'].min(),
            "resistance": recent_df['high'].max()
        }

    @staticmethod
    def get_price_relative_to_ema(df: pd.DataFrame) -> pd.Series:
        """
        Returns a score based on where price is relative to key EMAs.
        Positive: Price > EMA20 > EMA50 > EMA200 (Strong Bullish)
        """
        scores = []
        for i in range(len(df)):
            close = df['close'].iloc[i]
            e20 = df['ema_20'].iloc[i] if 'ema_20' in df.columns else close
            e50 = df['ema_50'].iloc[i] if 'ema_50' in df.columns else close
            e200 = df['ema_200'].iloc[i] if 'ema_200' in df.columns else close
            
            if close > e20 > e50 > e200:
                scores.append(1.0) # Strong Bullish
            elif close < e20 < e50 < e200:
                scores.append(-1.0) # Strong Bearish
            else:
                scores.append(0.0) # Mixed/Ranging
        
        return pd.Series(scores, index=df.index)
