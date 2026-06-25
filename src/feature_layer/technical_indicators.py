import pandas as pd
import ta
from typing import Dict


class TechnicalIndicators:
    """
    Calculates standard technical indicators using the 'ta' library.
    Replaces pandas_ta which is incompatible with Python 3.11.
    """

    @staticmethod
    def compute_all(df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all required technical indicators and return them as a DataFrame.
        Expected df columns: ['open', 'high', 'low', 'close', 'volume']
        """
        # Ensure we have a copy to avoid modifying the original df
        df = df.copy()

        # Validate required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # 1. Exponential Moving Averages (EMA)
        df['ema_20'] = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator()
        df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
        df['ema_200'] = ta.trend.EMAIndicator(df['close'], window=200).ema_indicator()

        # 2. RSI (14)
        df['rsi_14'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()

        # 3. MACD (12, 26, 9)
        macd = ta.trend.MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
        df['macd_line'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_histogram'] = macd.macd_diff()

        # 4. ATR (14)
        df['atr_14'] = ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=14
        ).average_true_range()

        # 5. Bollinger Bands (20, 2)
        bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_mid'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()

        # 6. Stochastic Oscillator
        stoch = ta.momentum.StochasticOscillator(
            df['high'], df['low'], df['close'], window=14, smooth_window=3
        )
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()

        # 7. Volume indicators
        df['volume_sma_20'] = ta.trend.SMAIndicator(df['volume'], window=20).sma_indicator()
        df['volume_ratio'] = df['volume'] / df['volume_sma_20'].replace(0, 1)

        # 8. Price momentum
        df['momentum_10'] = df['close'].pct_change(periods=10) * 100

        # 9. Volatility score (normalized ATR)
        df['volatility_score'] = (
            df['atr_14'] / df['close'].replace(0, float('nan')) * 100
        ).fillna(0)

        # Drop rows with NaN from indicator warmup period
        df.dropna(subset=['ema_200', 'rsi_14', 'macd_line', 'atr_14'], inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df

    @staticmethod
    def get_latest(df: pd.DataFrame) -> Dict:
        """
        Return the latest row of computed indicators as a dictionary.
        """
        if df.empty:
            return {}
        return df.iloc[-1].to_dict()
