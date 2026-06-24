import pytest
from unittest.mock import MagicMock
from decimal import Decimal
from datetime import datetime, timezone


# ------------------------------------------------------------------ #
#  Mock DB Session
# ------------------------------------------------------------------ #
@pytest.fixture
def mock_db():
    """A MagicMock that behaves like a SQLAlchemy Session."""
    db = MagicMock()
    db.merge = MagicMock()
    db.commit = MagicMock()
    db.query = MagicMock()
    return db


# ------------------------------------------------------------------ #
#  Mock TechnicalFeature (Bullish)
# ------------------------------------------------------------------ #
@pytest.fixture
def mock_features():
    f = MagicMock()
    f.symbol           = 'EURUSD'
    f.timeframe        = 'H1'
    f.bar_time         = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    f.ema_20           = Decimal('1.08500')
    f.ema_50           = Decimal('1.08200')
    f.ema_200          = Decimal('1.07500')
    f.rsi_14           = Decimal('62.5')
    f.macd_histogram   = Decimal('0.00045')
    f.adx_14           = Decimal('28.0')
    f.atr_14           = Decimal('0.00850')
    f.volatility_score = Decimal('7.9')
    f.momentum_score   = Decimal('0.65')
    f.regime           = 'LONDON_BULLISH'
    f.trend_state      = 'BULLISH'
    return f


@pytest.fixture
def mock_features_bearish():
    f = MagicMock()
    f.symbol           = 'EURUSD'
    f.timeframe        = 'H1'
    f.bar_time         = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    f.ema_20           = Decimal('1.07800')
    f.ema_50           = Decimal('1.08200')
    f.ema_200          = Decimal('1.08800')
    f.rsi_14           = Decimal('38.0')
    f.macd_histogram   = Decimal('-0.00035')
    f.adx_14           = Decimal('32.0')
    f.atr_14           = Decimal('0.00750')
    f.volatility_score = Decimal('6.5')
    f.momentum_score   = Decimal('-0.55')
    f.regime           = 'LONDON_BEARISH'
    f.trend_state      = 'BEARISH'
    return f


# ------------------------------------------------------------------ #
#  Mock SentimentScore
# ------------------------------------------------------------------ #
@pytest.fixture
def mock_sentiment_neutral():
    s = MagicMock()
    s.symbol                    = 'EURUSD'
    s.combined_sentiment        = 0.0
    s.event_risk_score          = 0.0
    s.base_currency_sentiment   = 0.0
    s.quote_currency_sentiment  = 0.0
    return s


@pytest.fixture
def mock_sentiment_risky():
    """High-impact news event - event_risk_score is negative (penalty)."""
    s = MagicMock()
    s.symbol                    = 'EURUSD'
    s.combined_sentiment        = 0.2
    s.event_risk_score          = -50.0
    s.base_currency_sentiment   = 0.1
    s.quote_currency_sentiment  = -0.1
    return s


@pytest.fixture
def mock_sentiment_positive():
    s = MagicMock()
    s.symbol                    = 'EURUSD'
    s.combined_sentiment        = 0.8
    s.event_risk_score          = 0.0
    s.base_currency_sentiment   = 0.7
    s.quote_currency_sentiment  = -0.3
    return s
