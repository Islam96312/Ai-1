from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.settings import settings
from database.schemas import Base
from src.data_layer.market_data_poller import MarketDataPoller
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database Setup
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables on startup (For MVP. In production use Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI Trading Decision Support System - Backend API"
)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running"
    }

@app.get("/api/v1/health")
async def health_check():
    """
    Checks if the system is healthy and connected to essential services.
    """
    health = {
        "status": "healthy",
        "database": "connected",
        "redis": "connected", # Simplified for now
    }
    try:
        # Simple DB check
        with engine.connect() as conn:
            conn.execute("SELECT 1")
    except Exception as e:
        health["status"] = "unhealthy"
        health["database"] = f"error: {str(e)}"
        
    return health

@app.post("/api/v1/market/poll")
async def trigger_poll(symbol: str = None, db: Session = Depends(get_db)):
    """
    Trigger market data polling via Celery worker.
    """
    from src.tasks import sync_market_data
    
    if symbol:
        task = sync_market_data.delay(symbol, settings.DEFAULT_TIMEFRAME)
    else:
        # Trigger for all symbols
        tasks = [sync_market_data.delay(s, settings.DEFAULT_TIMEFRAME) for s in settings.MONITORED_SYMBOLS]
        task = tasks[0] # Return first for reference
        
    return {"status": "task_queued", "task_id": task.id}

@app.post("/api/v1/news/sync/{symbol}")
async def sync_news(symbol: str, db: Session = Depends(get_db)):
    """
    Trigger news sync via Celery worker.
    """
    from src.tasks import sync_news_data
    task = sync_news_data.delay(symbol)
    return {"status": "task_queued", "task_id": task.id}

@app.post("/api/v1/ai/retrain/{symbol}")
async def retrain_model(symbol: str, timeframe: str = "H1", db: Session = Depends(get_db)):
    """
    Trigger AI model retraining in background.
    """
    from src.tasks import train_ai_model
    task = train_ai_model.delay(symbol, timeframe)
    return {"status": "training_started", "task_id": task.id}

@app.post("/api/v1/features/compute/{symbol}")
async def compute_features(symbol: str, timeframe: str = "H1", db: Session = Depends(get_db)):
    """
    Fetch latest bars, compute all technical features, and store them.
    """
    from src.data_layer.market_data_poller import MarketDataPoller
    from src.feature_layer.feature_builder import FeatureBuilder
    import pandas as pd

    # 1. Poll latest data first
    poller = MarketDataPoller(db)
    success = await poller.poll_symbol(symbol, timeframe)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data for {symbol}")

    # 2. Get data from DB as DataFrame
    from database.schemas import MarketBar
    query = db.query(MarketBar).filter(
        MarketBar.symbol == symbol, 
        MarketBar.timeframe == timeframe
    ).order_by(MarketBar.open_time.desc()).limit(500)
    
    bars = query.all()
    if not bars:
        raise HTTPException(status_code=404, detail="No bars found in DB to compute features")
    
    df = pd.DataFrame([
        {'open': b.open, 'high': b.high, 'low': b.low, 'close': b.close, 'volume': b.volume, 'open_time': b.open_time} 
        for b in bars
    ]).sort_values('open_time')

    # 3. Build Features
    builder = FeatureBuilder(db)
    feature_record = await builder.build_features(symbol, timeframe, df)
    
    return {
        "status": "success", 
        "symbol": symbol, 
        "timeframe": timeframe, 
        "last_updated": feature_record.bar_time,
        "rsi": feature_record.rsi_14,
        "regime": feature_record.trend_state
    }

@app.post("/api/v1/news/sync/{symbol}")
async def sync_news(symbol: str, db: Session = Depends(get_db)):
    """
    Complete news pipeline: Collect -> Parse Calendar -> Analyze Sentiment -> Score Risk.
    """
    from src.data_layer.symbol_mapper import SymbolMapper
    from src.news_layer.news_collector import NewsCollector
    from src.news_layer.calendar_parser import CalendarParser
    from src.news_layer.sentiment_analyzer import SentimentAnalyzer
    from src.news_layer.event_scorer import EventScorer

    base, quote = SymbolMapper.get_currencies(symbol)
    currencies = [base, quote]
    
    # 1. Collect news for both currencies
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
    
    # 2. Compute final risk and sentiment scores
    risk_status = scorer.calculate_risk_score(symbol)
    sentiments = scorer.compute_symbol_sentiment(symbol)
    await scorer.update_sentiment_store(symbol)
    
    return {
        "symbol": symbol,
        "risk": risk_status,
        "sentiment": sentiments,
        "status": "synced"
    }

@app.post("/api/v1/signals/generate/{symbol}")
async def generate_signal(symbol: str, timeframe: str = "H1", db: Session = Depends(get_db)):
    """
    Full AI Pipeline: Technicals + Sentiment -> AI Aggregator -> Human Explanation.
    """
    from src.data_layer.market_data_poller import MarketDataPoller
    from src.feature_layer.feature_builder import FeatureBuilder
    from src.news_layer.event_scorer import EventScorer
    from src.ai_layer.signal_aggregator import SignalAggregator
    from src.ai_layer.decision_explainer import DecisionExplainer
    from src.risk_layer.risk_engine import RiskEngine
    from src.risk_layer.risk_filters import RiskFilters
    from src.risk_layer.position_sizer import PositionSizer
    from database.schemas import TechnicalFeature, SentimentScore
    import pandas as pd

    # 1. Ensure we have fresh data and features
    poller = MarketDataPoller(db)
    await poller.poll_symbol(symbol, timeframe)
    
    # Fetch bars from DB
    from database.schemas import MarketBar
    bars = db.query(MarketBar).filter(MarketBar.symbol == symbol, MarketBar.timeframe == timeframe).order_by(MarketBar.open_time.desc()).limit(500).all()
    df = pd.DataFrame([{'open': b.open, 'high': b.high, 'low': b.low, 'close': b.close, 'volume': b.volume, 'open_time': b.open_time} for b in bars]).sort_values('open_time')
    
    builder = FeatureBuilder(db)
    features = await builder.build_features(symbol, timeframe, df)
    
    # 2. Ensure we have fresh sentiment/risk
    scorer = EventScorer(db)
    await scorer.update_sentiment_store(symbol)
    
    sentiment = db.query(SentimentScore).filter(SentimentScore.symbol == symbol).order_by(SentimentScore.timestamp.desc()).first()
    
    if not features or not sentiment:
        raise HTTPException(status_code=404, detail="Could not gather enough data to generate a signal")

    # 3. AI Aggregation
    aggregator = SignalAggregator()
    result = aggregator.aggregate(features, sentiment)
    
    # 4. Risk Layer
    risk_eng = RiskEngine()
    levels = risk_eng.calculate_levels(symbol, result['direction'], df.iloc[-1]['close'], features)
    
    filters = RiskFilters()
    signal_data = {**result, **levels}
    approved, reason = filters.validate_trade(signal_data, sentiment, 0)
    
    # 5. Position Sizing
    sizer = PositionSizer()
    lot_size = sizer.calculate_lot_size(balance=10000.0, risk_amount_pct=0.01, sl_pips=levels['risk_pips'], symbol=symbol)
    
    # 6. Human Explanation
    explainer = DecisionExplainer()
    explanation = explainer.explain(symbol, result)
    
    return {
        "symbol": symbol,
        "direction": result['direction'],
        "decision": "EXECUTE" if approved else "BLOCK",
        "confidence": result['final_score'],
        "risk_status": {"approved": approved, "reason": reason},
        "trade_params": {**levels, "lot_size": lot_size},
        "explanation": explanation,
        "breakdown": result['components']
    }

@app.post("/api/v1/backtest/run/{symbol}")
async def run_backtest(symbol: str, timeframe: str = "H1", db: Session = Depends(get_db)):
    """
    Runs a historical backtest for a symbol and returns a performance report.
    """
    from src.backtest.backtest_engine import BacktestEngine
    from src.backtest.backtest_reporter import BacktestReporter
    from database.schemas import MarketBar
    import pandas as pd

    # 1. Get historical data
    bars = db.query(MarketBar).filter(MarketBar.symbol == symbol, MarketBar.timeframe == timeframe).order_by(MarketBar.open_time).all()
    if not bars:
        raise HTTPException(status_code=404, detail="No historical data found for backtest")
    
    df = pd.DataFrame([{'open': b.open, 'high': b.high, 'low': b.low, 'close': b.close, 'volume': b.volume, 'open_time': b.open_time} for b in bars])
    
    # We need to compute indicators for the whole dataframe for backtesting
    from src.feature_layer.technical_indicators import TechnicalIndicators
    df = TechnicalIndicators.compute_all(df)
    df['regime'] = "NEUTRAL" # Simplified for backtest
    
    # 2. Run Engine
    engine = BacktestEngine(initial_balance=10000.0)
    trades = engine.run(symbol, timeframe, df)
    
    # 3. Generate Report
    reporter = BacktestReporter()
    report = reporter.generate_report(trades, 10000.0)
    
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "report": report,
        "total_trades": len(trades),
        "trades_detail": trades[-10:] # Return last 10 trades
    }





if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
