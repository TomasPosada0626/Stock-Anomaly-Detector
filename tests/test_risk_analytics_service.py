import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from services.risk_analytics_service import (
    beta_alpha,
    correlation,
    max_drawdown,
    sharpe_ratio,
    summarize_risk,
    value_at_risk,
    volatility,
)


def test_summarize_risk_returns_expected_keys() -> None:
    idx = pd.date_range("2025-01-01", periods=100, freq="D")
    asset = pd.Series([0.001 * ((i % 7) - 3) for i in range(100)], index=idx)
    benchmark = pd.Series([0.0008 * ((i % 5) - 2) for i in range(100)], index=idx)

    risk = summarize_risk(asset, benchmark_returns=benchmark)

    expected_keys = {
        "Sharpe Ratio",
        "Sortino Ratio",
        "Maximum Drawdown",
        "Volatility",
        "Beta",
        "Alpha",
        "Correlation",
        "VaR 95%",
    }
    assert set(risk.keys()) == expected_keys


def test_risk_metrics_handle_empty_and_zero_variance() -> None:
    empty = pd.Series(dtype=float)
    assert volatility(empty) == 0.0
    assert sharpe_ratio(empty) == 0.0
    assert value_at_risk(empty) == 0.0
    assert max_drawdown(pd.Series(dtype=float)) == 0.0

    flat = pd.Series([0.0, 0.0, 0.0])
    beta, alpha = beta_alpha(flat, flat)
    assert beta == 0.0
    assert alpha == 0.0
    assert correlation(empty, empty) == 0.0
