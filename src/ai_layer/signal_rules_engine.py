import logging
from typing import Dict, Any
from database.schemas import TechnicalFeature, SentimentScore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SignalRulesEngine:
    """
    Expert system that provides technical scores based on explicit trading rules.
    """
    def evaluate(self, features: TechnicalFeature, sentiment: SentimentScore) -> Dict[str, Any]:
        """
        Returns a technical score (0-100) and a suggested direction.
        """
        buy_score = 0
        sell_score = 0
        reasons = []

        # 1. EMA Alignment (Trend)
        if features.ema_20 > features.ema_50 > features.ema_200:
            buy_score += 30
            reasons.append("Strong Bullish EMA Alignment")
        elif features.ema_20 < features.ema_50 < features.ema_200:
            sell_score += 30
            reasons.append("Strong Bearish EMA Alignment")

        # 2. RSI State
        if features.rsi_14 and 50 < features.rsi_14 < 70:
            buy_score += 20
            reasons.append("RSI in Bullish Zone")
        elif features.rsi_14 and 30 < features.rsi_14 < 50:
            sell_score += 20
            reasons.append("RSI in Bearish Zone")
        elif features.rsi_14 and features.rsi_14 < 30:
            buy_score += 10 # Oversold potential
            reasons.append("RSI Oversold")
        elif features.rsi_14 and features.rsi_14 > 70:
            sell_score += 10 # Overbought potential
            reasons.append("RSI Overbought")

        # 3. MACD Momentum
        if features.macd_histogram and features.macd_histogram > 0:
            buy_score += 20
            reasons.append("Positive MACD Momentum")
        elif features.macd_histogram and features.macd_histogram < 0:
            sell_score += 20
            reasons.append("Negative MACD Momentum")

        # 4. Trend Strength (ADX)
        if features.adx_14 and features.adx_14 > 25:
            # Boost the winner
            if buy_score > sell_score:
                buy_score += 15
            else:
                sell_score += 15
            reasons.append("Strong Trend Confirmed by ADX")

        # Determine direction and final score
        if buy_score > sell_score:
            direction = "BUY"
            final_score = buy_score
        elif sell_score > buy_score:
            direction = "SELL"
            final_score = sell_score
        else:
            direction = "HOLD"
            final_score = 50

        return {
            "direction": direction,
            "score": min(final_score, 100),
            "reasons": reasons
        }
