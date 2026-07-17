from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from config import USE_SQLALCHEMY_REPOSITORIES

try:
    from repositories.sqlalchemy_domain_repositories import SqlPortfolioRepository
except Exception:  # pragma: no cover - optional dependency
    SqlPortfolioRepository = None  # type: ignore[assignment]


@dataclass(frozen=True)
class PositionInput:
    username: str
    ticker: str
    quantity: float
    buy_price: float
    buy_date: str


class PortfolioService:
    def __init__(self, db_path: str = "storage/quantvision.db", use_sqlalchemy: bool = USE_SQLALCHEMY_REPOSITORIES) -> None:
        self.db_path = db_path
        self._repo = None
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        if use_sqlalchemy and SqlPortfolioRepository is not None:
            try:
                self._repo = SqlPortfolioRepository()
            except Exception:
                self._repo = None
        self.initialize()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def initialize(self) -> None:
        if self._repo is not None:
            return
        conn = self._conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ticker TEXT NOT NULL,
                quantity REAL NOT NULL,
                buy_price REAL NOT NULL,
                buy_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    def add_position(self, data: PositionInput) -> int:
        if self._repo is not None:
            return self._repo.add_position(
                username=data.username,
                ticker=data.ticker,
                quantity=float(data.quantity),
                buy_price=float(data.buy_price),
                buy_date=data.buy_date,
            )
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO portfolio_positions (username, ticker, quantity, buy_price, buy_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data.username,
                data.ticker.upper(),
                float(data.quantity),
                float(data.buy_price),
                data.buy_date,
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        row_id = int(cur.lastrowid)
        conn.close()
        return row_id

    def remove_position(self, position_id: int, username: str) -> None:
        if self._repo is not None:
            self._repo.remove_position(position_id=position_id, username=username)
            return
        conn = self._conn()
        conn.execute(
            "DELETE FROM portfolio_positions WHERE id = ? AND username = ?",
            (position_id, username),
        )
        conn.commit()
        conn.close()

    def list_positions(self, username: str) -> pd.DataFrame:
        if self._repo is not None:
            return self._repo.list_positions(username=username)
        conn = self._conn()
        df = pd.read_sql_query(
            "SELECT id, ticker, quantity, buy_price, buy_date FROM portfolio_positions WHERE username = ? ORDER BY buy_date ASC",
            conn,
            params=(username,),
        )
        conn.close()
        return df

    def compute_portfolio_metrics(self, username: str, latest_prices: dict[str, float]) -> dict[str, float]:
        positions = self.list_positions(username)
        if positions.empty:
            return {
                "Invested Capital": 0.0,
                "Current Value": 0.0,
                "PnL": 0.0,
                "ROI %": 0.0,
            }

        positions = positions.copy()
        positions["current_price"] = positions["ticker"].map(latest_prices).fillna(0.0)
        positions["invested"] = positions["quantity"] * positions["buy_price"]
        positions["current_value"] = positions["quantity"] * positions["current_price"]

        invested = float(positions["invested"].sum())
        current_value = float(positions["current_value"].sum())
        pnl = current_value - invested
        roi = (pnl / invested * 100) if invested > 0 else 0.0

        return {
            "Invested Capital": invested,
            "Current Value": current_value,
            "PnL": pnl,
            "ROI %": roi,
        }
