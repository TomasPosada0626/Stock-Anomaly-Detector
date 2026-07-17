import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from services.backtesting_service import BacktestingService


def test_backtesting_service_runs_simple_strategy() -> None:
    idx = pd.date_range("2025-01-01", periods=8, freq="D")
    df = pd.DataFrame(
        {
            "Close": [100, 98, 95, 102, 108, 104, 110, 115],
            "buy_signal": [False, True, False, False, False, False, False, False],
            "sell_signal": [False, False, False, False, True, False, False, False],
        },
        index=idx,
    )
    svc = BacktestingService()
    result = svc.run_simple_strategy(df, "buy_signal", "sell_signal")
    assert set(result.keys()) == {
        "Return %",
        "Trades",
        "Win Rate %",
        "Buy & Hold %",
        "Max Drawdown %",
    }
    assert result["Trades"] >= 1


def test_backtesting_service_handles_invalid_input() -> None:
    svc = BacktestingService()
    result = svc.run_simple_strategy(pd.DataFrame(), "buy", "sell")
    assert result["Return %"] == 0.0
    assert result["Trades"] == 0.0
