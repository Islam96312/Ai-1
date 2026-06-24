import pandas as pd
from src.data_layer.mt5_connector import mt5_connector
from config.settings import settings

class MultiTimeframeAnalyzer:
    """
    Analyzes multiple timeframes to determine the overall trend bias.
    """
    TF_HIERARCHY = {
        "M1": "M5",
        "M5": "M15",
        "M15": "M30",
        "M30": "H1",
        "H1": "H4",
        "H4": "D1",
        "D1": "W1"
    }

    @staticmethod
    def get_higher_tf_bias(symbol: str, current_tf: str) -> str:
        """
        Determines bias (Bullish/Bearish/Neutral) from the higher timeframe.
        """
        higher_tf = MultiTimeframeAnalyzer.TF_HIERARCHY.get(current_tf.upper())
        if not higher_tf:
            return "NEUTRAL"

        # Fetch data for higher TF
        rates = mt5_connector.get_rates(symbol, higher_tf, count=100)
        if not rates:
            return "NEUTRAL"
        
        df = pd.DataFrame(rates)
        # Simple bias logic: Price vs EMA 50 on higher TF
        ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        current_close = df['close'].iloc[-1]
        
        if current_close > ema50 * 1.001: # 0.1% threshold
            return "BULLISH"
        elif current_close < ema50 * 0.999:
            return "BEARISH"
        else:
            return "NEUTRAL"
