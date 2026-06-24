from textblob import TextBlob
import logging
from typing import List, Dict
from sqlalchemy.orm import Session
from database.schemas import NewsEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """
    Advanced Sentiment Analyzer with Financial Lexicon.
    """
    # Financial keywords that usually shift sentiment in Forex
    FINANCIAL_LEXICON = {
        "hawkish": 0.5,
        "rate hike": 0.6,
        "inflation rise": -0.3,
        "gdp growth": 0.4,
        "dovish": -0.5,
        "rate cut": -0.6,
        "recession": -0.7,
        "economic slowdown": -0.4,
        "surplus": 0.3,
        "deficit": -0.3,
        "bullish": 0.5,
        "bearish": -0.5
    }

    def __init__(self, db_session: Session):
        self.db = db_session

    def analyze_text(self, text: str) -> float:
        """
        Analyzes text using a combination of TextBlob and a Financial Lexicon.
        """
        if not text:
            return 0.0
        
        # 1. Base sentiment from TextBlob
        blob_score = TextBlob(text).sentiment.polarity
        
        # 2. Lexicon-based boost
        lexicon_score = 0.0
        text_lower = text.lower()
        matches = 0
        
        for word, weight in self.FINANCIAL_LEXICON.items():
            if word in text_lower:
                lexicon_score += weight
                matches += 1
        
        # Average lexicon boost
        avg_lexicon = lexicon_score / matches if matches > 0 else 0.0
        
        # Final Score: Weighted average (Lexicon is more reliable for finance)
        final_score = (blob_score * 0.3) + (avg_lexicon * 0.7)
        
        # Clip between -1 and 1
        return max(-1.0, min(1.0, final_score))

    def update_news_sentiment(self, currency: str):
        """
        Fetches stored news for a currency and updates their sentiment scores.
        """
        news_items = self.db.query(NewsEvent).filter(
            NewsEvent.currency == currency, 
            NewsEvent.sentiment_score == None
        ).all()
        
        for item in news_items:
            text_to_analyze = f"{item.event_title} {item.sentiment_raw if item.sentiment_raw else ''}"
            score = self.analyze_text(text_to_analyze)
            item.sentiment_score = score
        
        self.db.commit()
        return len(news_items)
