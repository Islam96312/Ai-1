"""
FastAPI Backend — AI Trading Decision Support System
=====================================================
Fixes & Improvements vs. original:
  1. Health check now tests Redis connection (was always returning 'connected').
  2. /signals/generate — SentimentScore dummy now sets timestamp explicitly
     (SQLAlchemy ORM objects don't apply server_default on transient instances).
  3. /features/compute — returns richer response (all key indicators, not just 3).
  4. All endpoints wrapped with proper HTTPException propagation.
  5. Startup event logs registered routes for easy debugging.
  6. CORS middleware added (required for dashboard on different port).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from database.schemas import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Database ──────────────────────────────────────────────────────────
engine       = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


# ── App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI Trading Decision Support System — Backend API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Startup ───────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    logger.info("=== Registered routes ===")
    for route in app.routes:
        methods = getattr(route, "methods", None)
        logger.info("  %-8s %s", ",".join(methods) if methods else "-", route.path)


# ======================================================================
#  Endpoints
# ======================================================================

@app.get("/")
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status":  "running",
        "docs":    "/docs",
    }


@app.get("/api/v1/health")
async def health_check():
    """
    Checks connectivity to PostgreSQL and Redis.
    Returns overall status + per-service status.
    """
    health: dict = {"status": "healthy", "database": "connected", "redis": "disconnected"}

    # ── Database check ───────────────────────────────────────────────
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health["database"] = "connected"
    except Exception as exc:
        health["status"]   = "degraded"
        health["database"] = f"error: {exc}"

    # ── Redis check ──────────────────────────────────────────────────
    try:
        import redis as redis_lib
        r = redis_lib.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=getattr(settings, "REDIS_DB", 0),
            socket_connect_timeout=2,
        )
        r.ping()
        health["redis"] = "connected"
    except Exception as exc:
        health["status"] = "degraded"
        health["redis"]  = f"error: {exc}"

    return health


@app.post("/api/v1/market/poll")
async def trigger_poll(symbol: str = None, db: Session = Depends(get_db)):
    """
    Trigger market data polling via Celery.
    - With ?symbol=EURUSD  queues one task.
    - Without symbol       queues tasks for all MONITORED_SYMBOLS.
    """
    from src.tasks import sync_market_data

    if symbol:
        symbol = symbol.upper()
        task = sync_market_data.delay(symbol, settings.DEFAULT_TIMEFRAME)
        return {"status": "task_queued", "task_id": task.id, "symbol": symbol}

    tasks = [
        sync_market_data.delay(s, settings.DEFAULT_TIMEFRAME)
        for s in settings.MONITORED_SYMBOLS
    ]
    return {
        "status":   "tasks_queued",
        "count":    len(tasks),
        "symbols":  settings.MONITORED_SYMBOLS,
        "task_ids": [t.id for t in tasks],
    }


@app.post("/api/v1/news/sync/{symbol}")
async def sync_news(symbol: str, db: Session = Depends(get_db)):
    """Trigger news & sentiment sync via Celery."""
    from src.tasks import sync_news_data

    symbol = symbol.upper()
    task   = sync_news_data.delay(symbol)
    return {"status": "task_queued", "task_id": task.id, "symbol": symbol}


@app.post("/api/v1/features/compute/{symbol}")
async def compute_features(symbol: str, db: Session = Depends(get_db)):
    """
    Compute technical features for the latest bars of a symbol and persist them.
    Returns key indicator values for quick verification.
    """
    symbol = symbol.upper()
    try:
        from src.feature_layer.feature_builder import FeatureBuilder

        builder = FeatureBuilder(db)
        result  = builder.build_features(symbol, settings.DEFAULT_TIMEFRAME)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Not enough bars for {symbol}. "
                    f"Run POST /api/v1/market/poll?symbol={symbol} first."
                ),
            )

        def _f(v):
            return round(float(v), 6) if v is not None else None

        return {
            "status":    "success",
            "symbol":    symbol,
            "timeframe": settings.DEFAULT_TIMEFRAME,
            "indicators": {
                "ema_20":         _f(result.ema_20),
                "ema_50":         _f(result.ema_50),
                "ema_200":        _f(result.ema_200),
                "rsi_14":         _f(result.rsi_14),
                "macd_line":      _f(result.macd_line),
                "macd_histogram": _f(result.macd_histogram),
                "atr_14":         _f(result.atr_14),
                "adx_14":         _f(result.adx_14),
            },
            "context": {
                "regime":     result.regime,
                "trend_state": result.trend_state,
                "momentum":   _f(result.momentum_score),
                "volatility": _f(result.volatility_score),
            },
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Feature computation error for %s: %s", symbol, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/signals/generate/{symbol}")
async def generate_signal(symbol: str, db: Session = Depends(get_db)):
    """
    Run the full AI pipeline and return a trading signal.

    Pipeline: Features → Signal Aggregator → Risk Engine → Explainer
    """
    symbol = symbol.upper()
    try:
        from database.schemas import SentimentScore, TechnicalFeature
        from src.ai_layer.decision_explainer import DecisionExplainer
        from src.ai_layer.signal_aggregator import SignalAggregator
        from src.risk_layer.risk_engine import RiskEngine

        # ── 1. Load latest features ──────────────────────────────────
        features = (
            db.query(TechnicalFeature)
            .filter(
                TechnicalFeature.symbol    == symbol,
                TechnicalFeature.timeframe == settings.DEFAULT_TIMEFRAME,
            )
            .order_by(TechnicalFeature.bar_time.desc())
            .first()
        )
        if features is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No features found for {symbol}. "
                    f"Run POST /api/v1/features/compute/{symbol} first."
                ),
            )

        # ── 2. Load or create neutral sentiment ──────────────────────
        sentiment = (
            db.query(SentimentScore)
            .filter(SentimentScore.symbol == symbol)
            .order_by(SentimentScore.timestamp.desc())
            .first()
        )
        if sentiment is None:
            # FIX: timestamp must be set explicitly on transient ORM objects;
            # server_default only runs on INSERT, not on in-memory instances.
            sentiment = SentimentScore(
                symbol=symbol,
                timestamp=datetime.now(tz=timezone.utc),
                combined_sentiment=0.0,
                event_risk_score=0.0,
                base_currency_sentiment=0.0,
                quote_currency_sentiment=0.0,
                next_high_impact_minutes=None,
            )

        # ── 3. Aggregate signal ──────────────────────────────────────
        aggregator = SignalAggregator()
        result     = aggregator.aggregate(features, sentiment)

        # ── 4. Risk levels (only when actionable + MT5 available) ────
        trade_params: dict = {}
        if result["decision"] in ("EXECUTE", "ALERT") and result["direction"] != "HOLD":
            try:
                from src.data_layer.mt5_connector import mt5_connector

                tick          = mt5_connector.get_symbol_info(symbol)
                current_price = float(tick.get("ask", 0)) if tick else 0.0

                if current_price > 0:
                    risk_engine  = RiskEngine()
                    trade_params = risk_engine.calculate_levels(
                        symbol, result["direction"], current_price, features
                    )
            except Exception as risk_exc:
                logger.warning("Risk levels skipped (MT5 unavailable): %s", risk_exc)

        # ── 5. Explanation ───────────────────────────────────────────
        explanation = DecisionExplainer.explain(symbol, result)

        return {
            "symbol":       symbol,
            "decision":     result["decision"],
            "direction":    result["direction"],
            "confidence":   result["final_score"],
            "explanation":  explanation,
            "breakdown":    result["components"],
            "trade_params": trade_params,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Signal generation error for %s: %s", symbol, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/model/train/{symbol}")
async def train_model(symbol: str, db: Session = Depends(get_db)):
    """Trigger ML model retraining via Celery worker."""
    from src.tasks import train_ai_model

    symbol = symbol.upper()
    task   = train_ai_model.delay(symbol, settings.DEFAULT_TIMEFRAME)
    return {
        "status":  "task_queued",
        "task_id": task.id,
        "symbol":  symbol,
        "message": "Monitor progress in Celery worker logs.",
    }
