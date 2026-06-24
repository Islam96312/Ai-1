import pytest
import numpy as np
import pandas as pd
from datetime import timezone
from unittest.mock import patch, MagicMock
from src.feature_layer.feature_builder import FeatureBuilder


def make_bars_df(n: int = 100) -> pd.DataFrame:
    np.random.seed(42)
    close = 1.08 + np.cumsum(np.random.randn(n) * 0.0005)
    times = pd.date_range('2026-01-01', periods=n, freq='h', tz=timezone.utc)
    return pd.DataFrame({
        'open_time': times,
        'open':      close - 0.0002,
        'high':      close + 0.0005,
        'low':       close - 0.0005,
        'close':     close,
        'volume':    np.random.randint(100, 1000, n).astype(float),
    })


class TestFeatureBuilder:
    def test_build_returns_feature_record(self, mock_db):
        with patch('src.feature_layer.multi_timeframe'
                   '.MultiTimeframeAnalyzer.get_higher_tf_bias',
                   return_value='BULLISH'):
            builder = FeatureBuilder(mock_db)
            result  = builder.build_features('EURUSD', 'H1', make_bars_df(100))
        assert result is not None

    def test_db_merge_and_commit_called(self, mock_db):
        with patch('src.feature_layer.multi_timeframe'
                   '.MultiTimeframeAnalyzer.get_higher_tf_bias',
                   return_value='NEUTRAL'):
            builder = FeatureBuilder(mock_db)
            builder.build_features('EURUSD', 'H1', make_bars_df(100))
        mock_db.merge.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_short_df_returns_none(self, mock_db):
        """Less than 50 bars => return None gracefully."""
        builder = FeatureBuilder(mock_db)
        result  = builder.build_features('EURUSD', 'H1', make_bars_df(10))
        assert result is None

    def test_no_df_loads_from_db(self, mock_db):
        """bars_df=None => query DB. Empty DB => None (not enough bars)."""
        (mock_db.query.return_value
               .filter.return_value
               .order_by.return_value
               .limit.return_value
               .all.return_value) = []
        builder = FeatureBuilder(mock_db)
        result  = builder.build_features('EURUSD', 'H1', None)
        assert result is None
