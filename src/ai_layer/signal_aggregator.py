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
        # 1. Technical Score
        tech_res = self.rules_engine.evaluate(features, sentiment)
        tech_score = tech_res['score']

        # 2. Higher TF Bias
        htf_score = 50
        if features.regime:
            if 'BULLISH' in features.regime.upper():
                htf_score = 80
            elif 'BEARISH' in features.regime.upper():
                htf_score = 20

        # 3. News Sentiment (scale -1..1 -> 0..100)
        raw_sentiment = float(sentiment.combined_sentiment) if sentiment.combined_sentiment else 0.0
        news_score = 50 + (raw_sentiment * 50)

        # 4. Risk Score - FIX: event_risk_score is negative when risky (e.g. -100)
        # risk_score = 100 + event_risk_score, clamped to [0, 100]
        raw_risk = float(sentiment.event_risk_score) if sentiment.event_risk_score else 0.0
        risk_score = max(0.0, min(100.0, 100.0 + raw_risk))

        # FINAL WEIGHTED SCORE
        final_score = (
            (tech_score  * 0.45) +
            (htf_score   * 0.25) +
            (news_score  * 0.20) +
            (risk_score  * 0.10)
        )

        if final_score >= 70:
            decision = 'EXECUTE'
        elif final_score >= 50:
            decision = 'ALERT'
        else:
            decision = 'HOLD'

        return {
            'decision': decision,
            'direction': tech_res['direction'],
            'final_score': round(final_score, 2),
            'reasons': tech_res['reasons'],
            'components': {
                'technical': round(tech_score, 2),
                'htf_bias':  round(htf_score, 2),
                'news':      round(news_score, 2),
                'risk':      round(risk_score, 2),
            }
        }
