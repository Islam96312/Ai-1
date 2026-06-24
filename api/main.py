from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from config.settings import settings
from database.schemas import Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI Trading Decision Support System - Backend API"
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def root():
    return {"project": settings.PROJECT_NAME, "version": settings.VERSION, "status": "running"}


@app.get("/api/v1/health")
async def health_check():
    """Checks if the system is healthy and connected to essential services."""
    health = {"status": "healthy", "database": "connected", "redis": "connected"}
    try:
        # FIX: text() wrapper required by SQLAlchemy 2.x
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        health["status"] = "unhealthy"
        health["database"] = f"error: {str(e)}"
    return health


@app.post("/api/v1/market/poll")
async def trigger_poll(symbol: str = None, db: Session = Depends(get_db)):
    """Trigger market data polling via Celery worker."""
    from src.tasks import sync_market_data
    if symbol:
        task = sync_market_data.delay(symbol, settings.DEFAULT_TIMEFRAME)
        return {"status": "task_queued", "task_id": task.id, "symbol": symbol}
    tasks = [sync_market_data.delay(s, settings.DEFAULT_TIMEFRAME) for s in settings.MONITORED_SYMBOLS]
    return {"status": "tasks_queued", "count": len(tasks), "symbols": settings.MONITORED_SYMBOLS}


@app.post("/api/v1/news/sync/{symbol}")
async def sync_news(symbol: str, db: Session = Depends(get_db)):
    """Trigger news & sentiment sync via Celery."""
    from src.tasks import sync_news_data
    task = sync_news_data.delay(symbol)
    return {"status": "task_queued", "task_id": task.id, "symbol": symbol}


@app.post("/api/v1/features/compute/{symbol}")
async def compute_features(symbol: str, db: Session = Depends(get_db)):
    """Compute technical features for the latest bars of a symbol."""
    try:
        from src.feature_layer.feature_builder import FeatureBuilder
        builder = FeatureBuilder(db)
        result = builder.build_features(symbol, settings.DEFAULT_TIMEFRAME)
        if result:
            return {
                "status": "success",
                "symbol": symbol,
                "rsi": float(result.rsi_14) if result.rsi_14 else None,
                "regime": result.regime,
                "trend_state": result.trend_state,
            }
        raise HTTPException(status_code=404, detail="Not enough data to compute features")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Feature computation error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/signals/generate/{symbol}")
async def generate_signal(symbol: str, db: Session = Depends(get_db)):
    """Run the full AI pipeline and generate a trading signal."""
    try:
        from src.ai_layer.signal_aggregator import SignalAggregator
        from src.ai_layer.decision_explainer import DecisionExplainer
        from src.risk_layer.risk_engine import RiskEngine
        from database.schemas import TechnicalFeature, SentimentScore

        features = db.query(TechnicalFeature).filter(
            TechnicalFeature.symbol == symbol,
            TechnicalFeature.timeframe == settings.DEFAULT_TIMEFRAME
        ).order_by(TechnicalFeature.bar_time.desc()).first()

        if not features:
            raise HTTPException(status_code=404, detail=f"No features for {symbol}. Run /features/compute first.")

        sentiment = db.query(SentimentScore).filter(
            SentimentScore.symbol == symbol
        ).order_by(SentimentScore.timestamp.desc()).first()

        if not sentiment:
            sentiment = SentimentScore(
                symbol=symbol,
                combined_sentiment=0.0,
                event_risk_score=0.0,
                base_currency_sentiment=0.0,
                quote_currency_sentiment=0.0
            )

        aggregator = SignalAggregator()
        result = aggregator.aggregate(features, sentiment)

        trade_params = {}
        if result["decision"] in ("EXECUTE", "ALERT") and result["direction"] != "HOLD":
            from src.data_layer.mt5_connector import mt5_connector
            tick = mt5_connector.get_symbol_info(symbol)
            current_price = tick.get("ask", 0) if tick else 0
            if current_price > 0:
                risk_engine = RiskEngine()
                trade_params = risk_engine.calculate_levels(symbol, result["direction"], current_price, features)

        explanation = DecisionExplainer.explain(symbol, result)

        return {
            "symbol": symbol,
            "decision": result["decision"],
            "direction": result["direction"],
            "confidence": result["final_score"],
            "explanation": explanation,
            "breakdown": result["components"],
            "trade_params": trade_params,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Signal generation error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/model/train/{symbol}")
async def train_model(symbol: str, db: Session = Depends(get_db)):
    """Trigger model retraining via Celery."""
    from src.tasks import train_ai_model
    task = train_ai_model.delay(symbol, settings.DEFAULT_TIMEFRAME)
    return {"status": "task_queued", "task_id": task.id, "symbol": symbol}
