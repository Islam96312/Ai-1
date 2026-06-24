import pandas as pd
import pandas_ta as ta
from typing import Dict

class TechnicalIndicators:
    """
    Calculates standard technical indicators using pandas-ta.
    """
    @staticmethod
    def compute_all(df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all required technical indicators and return them as a DataFrame.
        Expected df columns: ['open', 'high', 'low', 'close', 'volume']
        """
        # Ensure we have a copy to avoid modifying the original df
        df = df.copy()

        # 1. Exponential Moving Averages (EMA)
        df['ema_20'] = ta.ema(df['close'], length=20)
        df['ema_50'] = ta.ema(df['close'], length=50)
        df['ema_200'] = ta.ema(df['close'], length=200)

        # 2. Relative Strength Index (RSI)
        df['rsi_14'] = ta.rsi(df['close'], length=14)

        # 3. MACD
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        df['macd_line'] = macd['MACD_12_26_9']
        df['macd_signal'] = macd['MACDs_12_26_9']
        df['macd_histogram'] = macd['MACDh_12_26_9']

        # 4. Average True Range (ATR) - Volatility
        df['atr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        # 5. Average Directional Index (ADX) - Trend Strength
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx_14'] = adx['ADX_14']

        # 6. Bollinger Bands
        bb = ta.bbands(df['close'], length=20, std=2)
        df['bb_lower'] = bb['BBL_20_2.0']
        df['bb_mid'] = bb['BBM_20_2.0']
        df['bb_upper'] = bb['BBU_20_2.0']

        return df
