import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from src.risk_layer.risk_engine import RiskEngine


@pytest.fixture
def engine():
    with patch('os.path.exists', return_value=False):
        return RiskEngine()


class TestRiskEngineBuy:
    def test_sl_below_entry(self, engine, mock_features):
        res = engine.calculate_levels('EURUSD', 'BUY', 1.09000, mock_features)
        assert res['stop_loss'] < res['entry'], 'BUY: SL must be below entry'

    def test_tp1_above_entry(self, engine, mock_features):
        res = engine.calculate_levels('EURUSD', 'BUY', 1.09000, mock_features)
        assert res['take_profit_1'] > res['entry'], 'BUY: TP1 must be above entry'

    def test_tp2_above_tp1(self, engine, mock_features):
        res = engine.calculate_levels('EURUSD', 'BUY', 1.09000, mock_features)
        assert res['take_profit_2'] > res['take_profit_1'], 'TP2 must be beyond TP1'

    def test_rr_positive(self, engine, mock_features):
        res = engine.calculate_levels('EURUSD', 'BUY', 1.09000, mock_features)
        assert res['risk_reward'] > 0, 'R:R must be positive'


class TestRiskEngineSell:
    def test_sl_above_entry(self, engine, mock_features):
        res = engine.calculate_levels('EURUSD', 'SELL', 1.09000, mock_features)
        assert res['stop_loss'] > res['entry'], 'SELL: SL must be above entry'

    def test_tp1_below_entry(self, engine, mock_features):
        res = engine.calculate_levels('EURUSD', 'SELL', 1.09000, mock_features)
        assert res['take_profit_1'] < res['entry'], 'SELL: TP1 must be below entry'


class TestRiskEngineEdgeCases:
    def test_zero_atr_fallback(self, engine):
        """When atr_14 is None, should use pip_size fallback without crashing."""
        f = MagicMock()
        f.atr_14 = None
        res = engine.calculate_levels('EURUSD', 'BUY', 1.09000, f)
        assert res['stop_loss'] < 1.09000

    def test_decimal_atr_no_type_error(self, engine, mock_features):
        """atr_14 from DB is Decimal - must not raise TypeError."""
        mock_features.atr_14 = Decimal('0.00850')
        res = engine.calculate_levels('EURUSD', 'BUY', 1.09000, mock_features)
        assert isinstance(res['risk_reward'], float)

    def test_xauusd_pip_size(self, engine, mock_features):
        """XAUUSD pip_size=0.1 - risk_pips should be reasonable."""
        mock_features.atr_14 = Decimal('1.50')
        res = engine.calculate_levels('XAUUSD', 'BUY', 2350.0, mock_features)
        assert res['risk_pips'] < 1000
