import pytest
from unittest.mock import MagicMock
from src.ai_layer.signal_aggregator import SignalAggregator


@pytest.fixture
def aggregator():
    return SignalAggregator()


class TestSignalAggregator:
    def test_output_keys_present(self, aggregator, mock_features, mock_sentiment_neutral):
        result = aggregator.aggregate(mock_features, mock_sentiment_neutral)
        for key in ('direction', 'final_score', 'decision', 'components'):
            assert key in result, f'Missing key: {key}'

    def test_score_within_bounds(self, aggregator, mock_features, mock_sentiment_neutral):
        result = aggregator.aggregate(mock_features, mock_sentiment_neutral)
        assert 0.0 <= result['final_score'] <= 100.0

    def test_risky_event_lowers_score(self, aggregator, mock_features,
                                      mock_sentiment_neutral, mock_sentiment_risky):
        """
        event_risk_score = -50 => risk_score = max(0, 100 + (-50)) = 50
        Must reduce final_score vs neutral (event_risk_score=0).
        """
        res_neutral = aggregator.aggregate(mock_features, mock_sentiment_neutral)
        res_risky   = aggregator.aggregate(mock_features, mock_sentiment_risky)
        assert res_risky['final_score'] <= res_neutral['final_score'], \
            'Risky event must lower or equal the final score'

    def test_decision_thresholds(self, aggregator, mock_features, mock_sentiment_positive):
        result = aggregator.aggregate(mock_features, mock_sentiment_positive)
        score  = result['final_score']
        if score >= 70:
            assert result['decision'] == 'EXECUTE'
        elif score >= 50:
            assert result['decision'] == 'ALERT'
        else:
            assert result['decision'] == 'HOLD'

    def test_component_keys_present(self, aggregator, mock_features, mock_sentiment_neutral):
        result = aggregator.aggregate(mock_features, mock_sentiment_neutral)
        for key in ('technical', 'htf_bias', 'news', 'risk'):
            assert key in result['components'], f'Missing component: {key}'
