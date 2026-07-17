import pandas as pd

from anomaly_methods import (
    detect_anomalies_iforest,
    detect_anomalies_lof,
    detect_anomalies_one_class_svm,
    detect_anomalies_zscore,
)


def test_zscore_handles_none_input() -> None:
    anomalies = detect_anomalies_zscore(None)
    assert isinstance(anomalies, pd.Series)
    assert anomalies.empty


def test_zscore_handles_empty_series(empty_returns_series: pd.Series) -> None:
    anomalies = detect_anomalies_zscore(empty_returns_series)
    assert anomalies.empty
    assert anomalies.dtype == bool


def test_iforest_handles_none_input() -> None:
    anomalies = detect_anomalies_iforest(None)
    assert isinstance(anomalies, pd.Series)
    assert anomalies.empty


def test_iforest_handles_all_nan_series() -> None:
    returns = pd.Series([None, None, None, None])
    anomalies = detect_anomalies_iforest(returns, contamination=0.1, random_state=42)
    assert len(anomalies) == len(returns)
    assert anomalies.dtype == bool
    assert anomalies.sum() == 0


def test_lof_handles_none_input() -> None:
    anomalies = detect_anomalies_lof(None)
    assert isinstance(anomalies, pd.Series)
    assert anomalies.empty


def test_ocsvm_handles_none_input() -> None:
    anomalies = detect_anomalies_one_class_svm(None)
    assert isinstance(anomalies, pd.Series)
    assert anomalies.empty


def test_lof_and_ocsvm_handle_nan_only_series() -> None:
    returns = pd.Series([float("nan"), float("nan"), float("nan")])
    lof = detect_anomalies_lof(returns)
    ocsvm = detect_anomalies_one_class_svm(returns)
    assert lof.sum() == 0
    assert ocsvm.sum() == 0


def test_iforest_preserves_index_on_nan_heavy_series(returns_with_nans: pd.Series) -> None:
    anomalies = detect_anomalies_iforest(returns_with_nans, contamination=0.3, random_state=42)
    assert list(anomalies.index) == list(returns_with_nans.index)


def test_detectors_work_on_large_series(large_returns_series: pd.Series) -> None:
    z = detect_anomalies_zscore(large_returns_series, threshold=3)
    i = detect_anomalies_iforest(large_returns_series, contamination=0.01, random_state=42)
    lof = detect_anomalies_lof(large_returns_series, contamination=0.01, n_neighbors=20)
    ocsvm = detect_anomalies_one_class_svm(large_returns_series, nu=0.01)

    assert len(z) == len(large_returns_series)
    assert len(i) == len(large_returns_series)
    assert len(lof) == len(large_returns_series)
    assert len(ocsvm) == len(large_returns_series)
