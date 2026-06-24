import logging
from typing import Dict, Any
from src.ai_layer.signal_rules_engine import SignalRulesEngine
from src.ai_layer.ml_model_service import MLModelService
from database.schemas import TechnicalFeature, SentimentScore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SignalAggregator:
    """
    Fuses Technical, ML, and Sentiment scores into a final decision.
    """
    def __init__(self):
        self.rules_engine = SignalRulesEngine()
        self.ml_service = MLModelService()

    def aggregate(self, features: TechnicalFeature, sentiment: SentimentScore) -> Dict[str, Any]:
        """
        Applies the final scoring formula.
        """
        # 1. Technical Score from Rules Engine
        tech_res = self.rules_engine.evaluate(features, sentiment)
        tech_score = tech_res['score']
        
        # 2. Higher TF Bias (Stored in features.regime in Sprint 2)
        # Logic: If regime contains 'BULLISH' -> 80, 'BEARISH' -> 20, else 50
        htf_score = 50
        if features.regime:
            if "BULLISH" in features.regime.upper(): htf_score = 80
            elif "BEARISH" in features.regime.upper(): htf_score = 20

        # 3. News Sentiment Score (Scaled to 0-100)
        # combined_sentiment is -1 to 1. Shift to 0-100.
        news_score = 50 + (sentiment.combined_sentiment * 50 if sentiment.combined_sentiment else 0)
        
        # 4. Risk Filter Score
        # If high risk, this should be negative or low
        risk_score = 100 if sentiment.event_risk_score == 0 else (100 + sentiment.event_risk_score)
        risk_score = max(0, min(100, risk_score))

        # FINAL WEIGHTED SCORE
        # FINAL_SCORE = (tech * 0.45) + (htf * 0.25) + (news * 0.20) + (risk * 0.10)
        final_score = (
            (tech_score * 0.45) + 
            (htf_score * 0.25) + 
            (news_score * 0.20) + 
            (risk_score * 0.10)
        )

        # Determine Decision
        if final_score >= 70:
            decision = "EXECUTE"
        elif final_score >= 50:
            decision = "ALERT"
        else:
            decision = "HOLD"

        # Final Direction
        direction = tech_res['direction']
        if direction == "HOLD" and final_score > 60:
            # If rules were neutral but combined score is high, we look at sentiment
            direction = "BUY" if sentiment.combined_sentiment > 0 else "SELL"

        return {
            "final_score": final_score,
            "decision": decision,
            "direction": direction,
            "components": {
                "technical": tech_score,
                "htf": htf_score,
                "news": news_score,
                "risk": risk_score
            },
            "reasons": tech_res['reasons']
        }
