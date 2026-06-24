import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from database.schemas import NewsEvent, SentimentScore
from src.data_layer.symbol_mapper import SymbolMapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EventScorer:
    """
    Calculates risk and sentiment scores for a specific symbol.
    """
    def __init__(self, db_session: Session):
        self.db = db_session

    def compute_symbol_sentiment(self, symbol: str) -> Dict[str, Any]:
        """
        Computes a combined sentiment score for a pair (Base - Quote).
        """
        base, quote = SymbolMapper.get_currencies(symbol)
        
        base_sentiment = self._get_avg_sentiment(base)
        quote_sentiment = self._get_avg_sentiment(quote)
        
        # Combined = Base positive and Quote negative is Bullish for the pair
        combined = base_sentiment - quote_sentiment
        
        return {
            "base_sentiment": base_sentiment,
            "quote_sentiment": quote_sentiment,
            "combined_sentiment": combined
        }

    def _get_avg_sentiment(self, currency: str) -> float:
        """
        Helper to get average sentiment of recent news for a currency.
        """
        # Only news from last 48 hours
        time_limit = datetime.now() - timedelta(hours=48)
        news = self.db.query(NewsEvent).filter(
            NewsEvent.currency == currency,
            NewsEvent.event_time >= time_limit,
            NewsEvent.sentiment_score != None
        ).all()
        
        if not news:
            return 0.0
        
        return sum(n.sentiment_score for n in news) / len(news)

    def calculate_risk_score(self, symbol: str) -> Dict[str, Any]:
        """
        Analyzes upcoming high impact events and returns risk status.
        """
        base, quote = SymbolMapper.get_currencies(symbol)
        now = datetime.now()
        
        # Look for HIGH impact events in the next 30 minutes
        window = now + timedelta(minutes=30)
        critical_events = self.db.query(NewsEvent).filter(
            NewsEvent.impact_level == "HIGH",
            NewsEvent.currency.in_([base, quote]),
            NewsEvent.event_time >= now,
            NewsEvent.event_time <= window
        ).all()
        
        if critical_events:
            # Find the nearest event
            nearest = min(critical_events, key=lambda x: x.event_time)
            mins_until = (nearest.event_time - now).total_seconds() / 60
            return {
                "risk_level": "HIGH",
                "block_trading": True if mins_until < 15 else False,
                "reason": f"High impact event {nearest.event_title} in {int(mins_until)} mins",
                "score": -100.0
            }
        
        return {
            "risk_level": "LOW",
            "block_trading": False,
            "reason": "No high-impact events nearby",
            "score": 0.0
        }

    async def update_sentiment_store(self, symbol: str):
        """
        Aggregates everything and saves to SentimentScore table.
        """
        sentiments = self.compute_symbol_sentiment(symbol)
        risk = self.calculate_risk_score(symbol)
        
        score_record = SentimentScore(
            symbol=symbol,
            timestamp=datetime.now(),
            base_currency_sentiment=sentiments['base_sentiment'],
            quote_currency_sentiment=sentiments['quote_sentiment'],
            combined_sentiment=sentiments['combined_sentiment'],
            event_risk_score=risk['score'],
            next_high_impact_minutes=0 # Could be calculated more precisely
        )
        self.db.merge(score_record)
        self.db.commit()
        return score_record
