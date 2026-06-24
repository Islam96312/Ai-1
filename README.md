# 🤖 AI Trading Decision Support System

A professional AI-powered trading assistant integrating **MetaTrader 5**, **machine learning**, and **fundamental analysis** to generate high-confidence trade signals.

## Architecture

```
┌─────────────────────────────────────────────┐
│             Streamlit Dashboard             │
└─────────────────────┬───────────────────────┘
                      │ HTTP
┌─────────────────────▼───────────────────────┐
│               FastAPI Backend               │
└──┬──────────┬──────────┬────────────────────┘
   │          │          │
   ▼          ▼          ▼
Data Layer  AI Layer  News Layer
(MT5)    (XGB+RF+LR) (NewsAPI+Calendar)
   │          │          │
   └──────────▼──────────┘
         PostgreSQL + Redis
```

## Layers

| Layer | Path | Description |
|---|---|---|
| Data | `src/data_layer/` | MT5 connection, bar polling |
| Feature | `src/feature_layer/` | Technical indicators, regime detection |
| AI | `src/ai_layer/` | ML ensemble, rules engine, signal scoring |
| News | `src/news_layer/` | News fetch, sentiment analysis, calendar |
| Risk | `src/risk_layer/` | SL/TP calculation, trade validation |
| Execution | `src/execution_layer/` | MT5 order execution with retry logic |
| Monitoring | `src/monitoring_layer/` | Telegram alerts, system watchdog |
| Backtest | `src/backtest/` | Walk-forward backtesting + reporting |

## Quick Start

### 1. Prerequisites

- Python 3.10+
- MetaTrader 5 Terminal (**Windows only** for `MetaTrader5` library)
- Docker & Docker Compose

### 2. Setup

```bash
git clone https://github.com/Islam96312/Ai-1.git
cd Ai-1
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
```

### 3. Start Infrastructure

```bash
docker compose up -d db redis
```

### 4. Run the System

```bash
# Full automated loop
python scripts/start_system.py

# API server only
uvicorn api.main:app --reload

# Celery worker (separate terminal)
celery -A src.worker.celery_app worker --loglevel=info

# Dashboard
streamlit run dashboard/app.py
```

### 5. Train the AI Model

```bash
curl -X POST "http://localhost:8000/api/v1/model/train/EURUSD"
```

## Signal Scoring Formula

```
Final Score = (Technical × 0.45) + (HTF Bias × 0.25) + (News × 0.20) + (Risk × 0.10)

EXECUTE  → Score ≥ 70
ALERT    → Score 50–69
HOLD     → Score < 50
```

## ⚠️ Important Notes

- `MetaTrader5` library is **Windows only**. Docker `app` profile requires Windows host.
- Set `ALERT_ONLY_MODE = True` in `scripts/start_system.py` to disable live execution during testing.
- ML model needs 100+ bars of computed features before training.

## Risk Warning

This system is for **decision support only**. Always verify signals manually before live trading.
