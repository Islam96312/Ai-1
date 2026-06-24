import requests
import logging
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from database.schemas import NewsEvent
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsCollector:
    """
    Fetches news from external APIs and stores them in the database.
    """
    def __init__(self, db_session: Session):
        self.db = db_session
        self.api_key = settings.NEWS_API_KEY # Should be added to settings.py

    def fetch_latest_news(self, currency: str) -> List[Dict[str, Any]]:
        """
        Fetches latest news related to a specific currency using NewsAPI.
        """
        if not self.api_key:
            logger.warning("NEWS_API_KEY not configured. Returning mock news for development.")
            return self._get_mock_news(currency)

        url = f"https://newsapi.org/v2/everything?q={currency}+forex&sortBy=publishedAt&apiKey={self.api_key}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('articles', [])
        except Exception as e:
            logger.error(f"Error fetching news for {currency}: {e}")
            return []

    def store_news(self, currency: str, articles: List[Dict[str, Any]]):
        """
        Parses and stores articles into the NewsEvent table.
        """
        for art in articles:
            try:
                # Convert ISO date to datetime
                pub_date = datetime.fromisoformat(art['publishedAt'].replace('Z', '+00:00'))
                
                event = NewsEvent(
                    event_time=pub_date,
                    currency=currency,
                    event_title=art['title'],
                    sentiment_raw=art['description'],
                    source=art['source'].get('name', 'Unknown')
                )
                self.db.merge(event)
            except Exception as e:
                logger.debug(f"Error storing article: {e}")
        
        self.db.commit()

    def _get_mock_news(self, currency: str) -> List[Dict[str, Any]]:
        """
        Provides mock data for testing when no API key is available.
        """
        return [
            {
                "title": f"{currency} Interest Rate Decision expected to be hawkish",
                "description": f"Markets are anticipating a rate hike for {currency} to fight inflation.",
                "publishedAt": datetime.now().isoformat(),
                "source": {"name": "MockForexNews"}
            },
            {
                "title": f"Economic slowdown hits {currency} zone",
                "description": f"GDP data shows a surprising drop in the {currency} region.",
                "publishedAt": datetime.now().isoformat(),
                "source": {"name": "MockForexNews"}
            }
        ]
