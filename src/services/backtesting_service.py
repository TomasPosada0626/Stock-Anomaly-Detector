from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class StrategyRules:
    buy_condition: Callable[[pd.Series, pd.Series | None], bool]
    sell_condition: Callable[[pd.Series, pd.Series | None], bool]
    take_profit_pct: float = 0.0


class BacktestingService:
    def run_simple_strategy(
        self,
        df: pd.DataFrame,
        buy_signal_col: str,
        sell_signal_col: str,
        initial_capital: float = 10_000.0,
    ) -> dict[str, float]:
        if df.empty or buy_signal_col not in df.columns or sell_signal_col not in df.columns:
            return {
                "Return %": 0.0,
                "Trades": 0.0,
                "Win Rate %": 0.0,
                "Buy & Hold %": 0.0,
                "Max Drawdown %": 0.0,
            }

        cash = initial_capital
        shares = 0.0
        trades = []
        equity_points = []
        entry_price = None

        for _, row in df.iterrows():
            price = float(row["Close"])
            if bool(row[buy_signal_col]) and cash > 0:
                shares = cash / price
                cash = 0.0
                entry_price = price
            elif bool(row[sell_signal_col]) and shares > 0:
                cash = shares * price
                shares = 0.0
                if entry_price is not None:
                    trades.append((price - entry_price) / entry_price)
                entry_price = None
            equity_points.append(cash + shares * price)

        final_value = equity_points[-1] if equity_points else initial_capital
        strat_return = ((final_value / initial_capital) - 1) * 100
        buy_hold = ((float(df["Close"].iloc[-1]) / float(df["Close"].iloc[0])) - 1) * 100
        wins = sum(1 for t in trades if t > 0)
        win_rate = (wins / len(trades) * 100) if trades else 0.0

        equity = pd.Series(equity_points, index=df.index[: len(equity_points)])
        peak = equity.cummax().replace(0.0, pd.NA)
        drawdown = ((equity - peak) / peak).fillna(0.0)

        return {
            "Return %": float(strat_return),
            "Trades": float(len(trades)),
            "Win Rate %": float(win_rate),
            "Buy & Hold %": float(buy_hold),
            "Max Drawdown %": float(drawdown.min() * 100),
        }

    def run_rule_based_strategy(
        self,
        df: pd.DataFrame,
        rules: StrategyRules,
        initial_capital: float = 10_000.0,
    ) -> dict[str, float | list[dict[str, float | str]]]:
        if df.empty or "Close" not in df.columns:
            return {
                "Return %": 0.0,
                "Trades": 0.0,
                "Win Rate %": 0.0,
                "Buy & Hold %": 0.0,
                "Max Drawdown %": 0.0,
                "Trade Log": [],
            }

        cash = initial_capital
        shares = 0.0
        entry_price: float | None = None
        trade_log: list[dict[str, float | str]] = []
        trade_returns: list[float] = []
        equity_points: list[float] = []

        previous_row: pd.Series | None = None
        for timestamp, row in df.iterrows():
            price = float(row["Close"])
            buy_signal = bool(rules.buy_condition(row, previous_row))
            sell_signal = bool(rules.sell_condition(row, previous_row))

            if shares > 0 and entry_price is not None and rules.take_profit_pct > 0:
                target = entry_price * (1 + rules.take_profit_pct / 100)
                if price >= target:
                    sell_signal = True

            if buy_signal and cash > 0:
                shares = cash / price
                cash = 0.0
                entry_price = price
                trade_log.append(
                    {
                        "Timestamp": str(timestamp),
                        "Action": "BUY",
                        "Price": price,
                        "Shares": shares,
                    }
                )
            elif sell_signal and shares > 0:
                cash = shares * price
                pnl_pct = 0.0
                if entry_price and entry_price > 0:
                    pnl_pct = ((price / entry_price) - 1) * 100
                    trade_returns.append(pnl_pct / 100)
                trade_log.append(
                    {
                        "Timestamp": str(timestamp),
                        "Action": "SELL",
                        "Price": price,
                        "Shares": shares,
                        "PnL %": pnl_pct,
                    }
                )
                shares = 0.0
                entry_price = None

            equity_points.append(cash + shares * price)
            previous_row = row

        final_value = equity_points[-1] if equity_points else initial_capital
        strat_return = ((final_value / initial_capital) - 1) * 100
        buy_hold = ((float(df["Close"].iloc[-1]) / float(df["Close"].iloc[0])) - 1) * 100
        wins = sum(1 for value in trade_returns if value > 0)
        win_rate = (wins / len(trade_returns) * 100) if trade_returns else 0.0

        equity = pd.Series(equity_points, index=df.index[: len(equity_points)])
        peak = equity.cummax().replace(0.0, pd.NA)
        drawdown = ((equity - peak) / peak).fillna(0.0)

        return {
            "Return %": float(strat_return),
            "Trades": float(len(trade_returns)),
            "Win Rate %": float(win_rate),
            "Buy & Hold %": float(buy_hold),
            "Max Drawdown %": float(drawdown.min() * 100),
            "Trade Log": trade_log,
        }
