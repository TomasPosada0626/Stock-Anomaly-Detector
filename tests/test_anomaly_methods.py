import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from anomaly_methods import detect_anomalies_iforest, detect_anomalies_zscore
from utils import rolling_quantile_anomaly


def test_zscore_detects_large_outliers() -> None:
    returns = pd.Series([0.01, 0.02, 0.03, 0.5, -0.6, 0.02, 0.01])
    anomalies = detect_anomalies_zscore(returns, threshold=1.5)
    assert anomalies.sum() == 2


def test_zscore_constant_series_has_no_anomalies() -> None:
    returns = pd.Series([0.02, 0.02, 0.02, 0.02])
    anomalies = detect_anomalies_zscore(returns, threshold=3)
    assert anomalies.sum() == 0


def test_zscore_preserves_input_index() -> None:
    idx = pd.date_range("2025-01-01", periods=5, freq="D")
    returns = pd.Series([0.01, 0.01, 0.04, 0.01, -0.05], index=idx)
    anomalies = detect_anomalies_zscore(returns, threshold=1.5)
    assert list(anomalies.index) == list(idx)


def test_iforest_detects_outliers() -> None:
    returns = pd.Series([0.01, 0.02, 0.03, 0.5, -0.6, 0.02, 0.01])
    anomalies = detect_anomalies_iforest(returns, contamination=0.2, random_state=42)
    assert anomalies.sum() >= 2


def test_iforest_handles_nans_and_preserves_shape() -> None:
    returns = pd.Series([0.01, None, 0.02, 0.03, None, 0.5, -0.6])
    anomalies = detect_anomalies_iforest(returns, contamination=0.3, random_state=42)
    assert len(anomalies) == len(returns)
    assert anomalies.dtype == bool
    assert not anomalies.iloc[1]
    assert not anomalies.iloc[4]


def test_iforest_is_deterministic_with_fixed_random_state() -> None:
    returns = pd.Series([0.01, 0.02, 0.03, 0.5, -0.6, 0.02, 0.01])
    first = detect_anomalies_iforest(returns, contamination=0.2, random_state=42)
    second = detect_anomalies_iforest(returns, contamination=0.2, random_state=42)
    assert first.equals(second)


def test_rolling_quantile_flags_extreme_spike() -> None:
    series = pd.Series([1, 2, 3, 100, 5, 6, 7, 8, 9, 10])
    anomalies = rolling_quantile_anomaly(series, window=3, quantile=0.95)
    assert anomalies.sum() >= 1


def test_rolling_quantile_returns_boolean_series() -> None:
    series = pd.Series([10, 11, 12, 13, 14])
    anomalies = rolling_quantile_anomaly(series, window=2, quantile=0.9)
    assert anomalies.dtype == bool
