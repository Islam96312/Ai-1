import logging
from src.worker import celery_app
from sqlalchemy.orm import sessionmaker
from api.main import SessionLocal
from src.data_layer.market_data_poller import MarketDataPoller
from src.news_layer.news_collector import NewsCollector
from src.news_layer.calendar_parser import CalendarParser
from src.news_layer.sentiment_analyzer import SentimentAnalyzer
from src.news_layer.event_scorer import EventScorer
from src.data_layer.symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.sync_market_data")
def sync_market_data(symbol: str, timeframe: str):
    """
    Background task to poll market data.
    """
    db = SessionLocal()
    try:
        import asyncio
        poller = MarketDataPoller(db)
        # Since poller.poll_symbol is async, we run it in a loop
        asyncio.run(poller.poll_symbol(symbol, timeframe))
        return f"Market data synced for {symbol}"
    finally:
        db.close()

@celery_app.task(name="tasks.sync_news_data")
def sync_news_data(symbol: str):
    """
    Background task to sync news, sentiment, and risk.
    """
    db = SessionLocal()
    try:
        base, quote = SymbolMapper.get_currencies(symbol)
        currencies = [base, quote]
        
        collector = NewsCollector(db)
        calendar = CalendarParser(db)
        analyzer = SentimentAnalyzer(db)
        scorer = EventScorer(db)
        
        # Sync Calendar
        cal_events = calendar.fetch_today_calendar()
        calendar.store_calendar_events(cal_events)
        
        # Sync News & Sentiment
        for curr in currencies:
            articles = collector.fetch_latest_news(curr)
            collector.store_news(curr, articles)
            analyzer.update_news_sentiment(curr)
        
        # Sync Risk Score
        import asyncio
        asyncio.run(scorer.update_sentiment_store(symbol))
        
        return f"News and sentiment synced for {symbol}"
    finally:
        db.close()

@celery_app.task(name="tasks.train_ai_model")
def train_ai_model(symbol: str, timeframe: str):
    """
    Background task to retrain the ML model.
    """
    db = SessionLocal()
    try:
        from src.ai_layer.model_trainer import ModelTrainer
        trainer = ModelTrainer(db)
        success = trainer.train_ensemble(symbol, timeframe)
        return f"Model training {'success' if success else 'failed'} for {symbol}"
    finally:
        db.close()
