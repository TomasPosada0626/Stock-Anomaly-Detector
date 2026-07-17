from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class WatchlistInput:
    username: str
    name: str


class WatchlistService:
    def __init__(self, db_path: str = "storage/quantvision.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def initialize(self) -> None:
        conn = self._conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(username, name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watchlist_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(watchlist_id, ticker),
                FOREIGN KEY(watchlist_id) REFERENCES watchlists(id)
            )
            """
        )
        conn.commit()
        conn.close()

    def create_watchlist(self, data: WatchlistInput) -> int:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO watchlists (username, name, created_at) VALUES (?, ?, ?)",
            (data.username, data.name.strip(), datetime.now(UTC).isoformat()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM watchlists WHERE username = ? AND name = ?",
            (data.username, data.name.strip()),
        ).fetchone()
        conn.close()
        return int(row[0])

    def delete_watchlist(self, watchlist_id: int, username: str) -> None:
        conn = self._conn()
        conn.execute(
            "DELETE FROM watchlist_items WHERE watchlist_id IN (SELECT id FROM watchlists WHERE id = ? AND username = ?)",
            (watchlist_id, username),
        )
        conn.execute("DELETE FROM watchlists WHERE id = ? AND username = ?", (watchlist_id, username))
        conn.commit()
        conn.close()

    def add_ticker(self, watchlist_id: int, ticker: str) -> None:
        conn = self._conn()
        conn.execute(
            "INSERT OR IGNORE INTO watchlist_items (watchlist_id, ticker, created_at) VALUES (?, ?, ?)",
            (watchlist_id, ticker.upper(), datetime.now(UTC).isoformat()),
        )
        conn.commit()
        conn.close()

    def remove_ticker(self, watchlist_id: int, ticker: str) -> None:
        conn = self._conn()
        conn.execute(
            "DELETE FROM watchlist_items WHERE watchlist_id = ? AND ticker = ?",
            (watchlist_id, ticker.upper()),
        )
        conn.commit()
        conn.close()

    def list_watchlists(self, username: str) -> pd.DataFrame:
        conn = self._conn()
        df = pd.read_sql_query(
            "SELECT id, name, created_at FROM watchlists WHERE username = ? ORDER BY created_at ASC",
            conn,
            params=(username,),
        )
        conn.close()
        return df

    def list_items(self, watchlist_id: int) -> pd.DataFrame:
        conn = self._conn()
        df = pd.read_sql_query(
            "SELECT ticker FROM watchlist_items WHERE watchlist_id = ? ORDER BY ticker ASC",
            conn,
            params=(watchlist_id,),
        )
        conn.close()
        return df
