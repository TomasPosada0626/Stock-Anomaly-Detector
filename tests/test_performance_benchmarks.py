import time

import pandas as pd

from anomaly_methods import (
    detect_anomalies_iforest,
    detect_anomalies_lof,
    detect_anomalies_one_class_svm,
    detect_anomalies_zscore,
)


def _run_and_measure(func, *args, **kwargs) -> tuple[pd.Series, float]:
    start = time.perf_counter()
    output = func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return output, elapsed


def test_anomaly_methods_performance_10k(large_returns_series: pd.Series) -> None:
    z_out, z_time = _run_and_measure(detect_anomalies_zscore, large_returns_series, 3.0)
    if_out, if_time = _run_and_measure(
        detect_anomalies_iforest,
        large_returns_series,
        contamination=0.01,
        random_state=42,
    )
    lof_out, lof_time = _run_and_measure(
        detect_anomalies_lof,
        large_returns_series,
        contamination=0.01,
        n_neighbors=20,
    )
    ocsvm_out, ocsvm_time = _run_and_measure(
        detect_anomalies_one_class_svm,
        large_returns_series,
        nu=0.01,
    )

    assert len(z_out) == 10_000
    assert len(if_out) == 10_000
    assert len(lof_out) == 10_000
    assert len(ocsvm_out) == 10_000

    # Conservative thresholds to avoid flaky CI while still catching regressions.
    assert z_time < 1.5
    assert if_time < 12.0
    assert lof_time < 6.0
    assert ocsvm_time < 6.0
