import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from services.backtesting_service import BacktestingService, StrategyRules


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


def test_backtesting_service_rule_based_strategy() -> None:
    idx = pd.date_range("2025-01-01", periods=10, freq="D")
    df = pd.DataFrame(
        {
            "Close": [100, 98, 96, 99, 101, 104, 102, 106, 108, 110],
            "RSI_14": [40, 35, 28, 32, 45, 55, 65, 72, 75, 78],
        },
        index=idx,
    )

    svc = BacktestingService()
    rules = StrategyRules(
        buy_condition=lambda row, prev: bool(row.get("RSI_14", 50) < 30),
        sell_condition=lambda row, prev: bool(row.get("RSI_14", 50) > 70),
        take_profit_pct=3.0,
    )
    result = svc.run_rule_based_strategy(df, rules=rules)
    assert "Trade Log" in result
    assert result["Trades"] >= 1


def test_backtesting_service_rule_based_handles_missing_close() -> None:
    svc = BacktestingService()
    rules = StrategyRules(
        buy_condition=lambda row, prev: False,
        sell_condition=lambda row, prev: False,
    )
    result = svc.run_rule_based_strategy(pd.DataFrame({"A": [1, 2]}), rules=rules)
    assert result["Return %"] == 0.0
