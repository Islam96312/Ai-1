from celery import Celery
from celery.schedules import crontab
from config.settings import settings

REDIS_URL = f'redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}'

celery_app = Celery(
    'trading_worker',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['src.tasks'],
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ------------------------------------------------------------------ #
#  Celery Beat Schedule — Automatic periodic tasks                    #
#  Run:  celery -A src.worker beat --loglevel=info                   #
# ------------------------------------------------------------------ #
celery_app.conf.beat_schedule = {
    # Poll market data every hour at :01 (H1 candle just closed)
    **{
        f'poll-{symbol.lower()}-h1': {
            'task':     'tasks.sync_market_data',
            'schedule': crontab(minute=1),          # every hour at XX:01
            'args':     (symbol, settings.DEFAULT_TIMEFRAME),
        }
        for symbol in settings.MONITORED_SYMBOLS
    },
    # Sync news & sentiment every 30 minutes
    **{
        f'news-{symbol.lower()}': {
            'task':     'tasks.sync_news_data',
            'schedule': crontab(minute='*/30'),
            'args':     (symbol,),
        }
        for symbol in settings.MONITORED_SYMBOLS
    },
    # Retrain models daily at 03:00 UTC (low-activity window)
    **{
        f'train-{symbol.lower()}-daily': {
            'task':     'tasks.train_ai_model',
            'schedule': crontab(hour=3, minute=0),
            'args':     (symbol, settings.DEFAULT_TIMEFRAME),
        }
        for symbol in settings.MONITORED_SYMBOLS
    },
}
