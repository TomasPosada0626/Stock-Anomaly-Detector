import builtins
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from ui.charts import (
    _resolve_close_column,
    build_anomaly_chart,
    build_candlestick_chart,
    build_comparison_chart,
    build_price_chart,
    build_volume_chart,
)


def test_build_price_chart_returns_figure_and_series() -> None:
    df = pd.DataFrame(
        {"Close": [10, 11, 12]}, index=pd.date_range("2025-01-01", periods=3, freq="D")
    )
    fig, y_data = build_price_chart(df, "AAPL")
    assert len(fig.data) >= 1
    assert len(y_data) == 3


def test_build_anomaly_chart_contains_points_and_line() -> None:
    df = pd.DataFrame(
        {"Close": [10, 11, 12, 13]}, index=pd.date_range("2025-01-01", periods=4, freq="D")
    )
    pts = df.iloc[[1, 3]].copy()
    pts["Method"] = ["Z-Score", "I-Forest"]
    y_data = df["Close"]

    fig = build_anomaly_chart(df, pts, y_data)
    assert len(fig.data) >= 2


def test_resolve_close_column_with_multiindex() -> None:
    idx = pd.date_range("2025-01-01", periods=3, freq="D")
    df = pd.DataFrame(
        {
            ("Open", "AAPL"): [9, 10, 11],
            ("Close", "AAPL"): [10, 11, 12],
        },
        index=idx,
    )
    close_col = _resolve_close_column(df)
    assert close_col == ("Close", "AAPL")


def test_build_price_chart_fallback_branch(monkeypatch) -> None:
    idx = pd.date_range("2025-01-01", periods=3, freq="D")
    df = pd.DataFrame({"Close": [10, 11, 12]}, index=idx)

    original_hasattr = builtins.hasattr

    def fake_hasattr(obj, name):
        if name == "values":
            return False
        return original_hasattr(obj, name)

    monkeypatch.setattr(builtins, "hasattr", fake_hasattr)

    fig, y_data = build_price_chart(df, "AAPL")
    assert len(fig.data) >= 1
    assert len(y_data) == 3


def test_build_anomaly_chart_fallback_branch(monkeypatch) -> None:
    df = pd.DataFrame(
        {"Close": [10, 11, 12, 13]}, index=pd.date_range("2025-01-01", periods=4, freq="D")
    )
    pts = df.iloc[[1, 3]].copy()
    pts["Method"] = ["Z-Score", "I-Forest"]
    y_data = df["Close"]

    original_hasattr = builtins.hasattr

    def fake_hasattr(obj, name):
        if name == "values":
            return False
        return original_hasattr(obj, name)

    monkeypatch.setattr(builtins, "hasattr", fake_hasattr)

    fig = build_anomaly_chart(df, pts, y_data)
    assert len(fig.data) >= 2


def test_build_candlestick_and_volume_charts() -> None:
    idx = pd.date_range("2025-01-01", periods=3, freq="D")
    df = pd.DataFrame(
        {
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.5, 12.5],
            "Volume": [1000, 1200, 1500],
        },
        index=idx,
    )
    candle = build_candlestick_chart(df, "AAPL")
    volume = build_volume_chart(df, "AAPL")
    assert len(candle.data) == 1
    assert len(volume.data) == 1


def test_build_comparison_chart_has_one_trace_per_column() -> None:
    idx = pd.date_range("2025-01-01", periods=3, freq="D")
    df = pd.DataFrame({"AAPL": [10, 11, 12], "MSFT": [20, 21, 22]}, index=idx)
    fig = build_comparison_chart(df, "Comparison")
    assert len(fig.data) == 2
