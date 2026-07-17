from __future__ import annotations

import pandas as pd


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
