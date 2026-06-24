import pytest
import datetime as dt_mod
from unittest.mock import patch, MagicMock
from src.risk_layer.risk_filters import RiskFilters


LONDON_HOUR = dt_mod.datetime(2026, 1, 1, 10, 0, tzinfo=dt_mod.timezone.utc)
OFF_HOUR    = dt_mod.datetime(2026, 1, 1,  3, 0, tzinfo=dt_mod.timezone.utc)


@pytest.fixture
def filters():
    with patch('os.path.exists', return_value=False):
        return RiskFilters()


@pytest.fixture
def good_signal():
    return {
        'symbol':      'EURUSD',
        'final_score': 72.0,
        'risk_reward': 1.5,
        'lot':         0.1,
        'risk_pips':   15.0,
    }


@pytest.fixture
def weak_signal():
    return {
        'symbol':      'EURUSD',
        'final_score': 55.0,
        'risk_reward': 1.5,
        'lot':         0.1,
        'risk_pips':   15.0,
    }


class TestRiskFiltersApproval:
    def test_good_signal_approved(self, filters, good_signal, mock_sentiment_neutral):
        with patch('src.risk_layer.risk_filters.datetime') as m:
            m.now = lambda tz=None: LONDON_HOUR
            approved, reason = filters.validate_trade(
                good_signal, mock_sentiment_neutral, [], 10000)
        assert approved is True
        assert reason == 'Approved'

    def test_low_confidence_rejected(self, filters, weak_signal, mock_sentiment_neutral):
        with patch('src.risk_layer.risk_filters.datetime') as m:
            m.now = lambda tz=None: LONDON_HOUR
            approved, reason = filters.validate_trade(
                weak_signal, mock_sentiment_neutral, [], 10000)
        assert approved is False
        assert 'Confidence' in reason

    def test_low_rr_rejected(self, filters, mock_sentiment_neutral):
        signal = {'symbol': 'EURUSD', 'final_score': 75.0,
                  'risk_reward': 0.8, 'lot': 0.1, 'risk_pips': 15.0}
        with patch('src.risk_layer.risk_filters.datetime') as m:
            m.now = lambda tz=None: LONDON_HOUR
            approved, reason = filters.validate_trade(
                signal, mock_sentiment_neutral, [], 10000)
        assert approved is False
        assert 'R:R' in reason

    def test_outside_hours_rejected(self, filters, good_signal, mock_sentiment_neutral):
        with patch('src.risk_layer.risk_filters.datetime') as m:
            m.now = lambda tz=None: OFF_HOUR
            approved, reason = filters.validate_trade(
                good_signal, mock_sentiment_neutral, [], 10000)
        assert approved is False
        assert 'hours' in reason.lower()

    def test_max_trades_rejected(self, filters, good_signal, mock_sentiment_neutral):
        open_trades = [{'symbol': 'GBPUSD', 'lot': 0.1, 'risk_pips': 10}] * 5
        with patch('src.risk_layer.risk_filters.datetime') as m:
            m.now = lambda tz=None: LONDON_HOUR
            approved, reason = filters.validate_trade(
                good_signal, mock_sentiment_neutral, open_trades, 10000)
        assert approved is False
        assert 'Max open trades' in reason

    def test_none_open_trades_no_crash(self, filters, mock_sentiment_neutral):
        """open_trades=None must default to [] without crashing."""
        signal = {'symbol': 'EURUSD', 'final_score': 30.0,
                  'risk_reward': 1.5, 'lot': 0.1, 'risk_pips': 10}
        with patch('src.risk_layer.risk_filters.datetime') as m:
            m.now = lambda tz=None: LONDON_HOUR
            approved, _ = filters.validate_trade(
                signal, mock_sentiment_neutral, None, 10000)
        assert approved is False


class TestCurrencyExtraction:
    def test_eurusd_split(self, filters):
        base, quote = filters._get_currencies('EURUSD')
        assert base == 'EUR' and quote == 'USD'

    def test_xauusd_split(self, filters):
        base, quote = filters._get_currencies('XAUUSD')
        assert base == 'XAU' and quote == 'USD'
