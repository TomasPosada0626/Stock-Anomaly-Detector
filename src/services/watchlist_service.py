from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config import USE_SQLALCHEMY_REPOSITORIES
from security.encryption import decrypt_value, encrypt_value

try:
    from repositories.sqlalchemy_domain_repositories import (
        SqlWatchlistRepository as _SqlWatchlistRepository,
    )
except Exception:  # pragma: no cover - optional dependency
    _SqlWatchlistRepository = None


@dataclass(frozen=True)
class WatchlistInput:
    username: str
    name: str


class WatchlistService:
    """Manage user watchlists and their ticker items."""

    def __init__(
        self,
        db_path: str = "storage/quantvision.db",
        use_sqlalchemy: bool = USE_SQLALCHEMY_REPOSITORIES,
    ) -> None:
        self.db_path = db_path
        self._encryption_key = os.getenv("DATA_ENCRYPTION_KEY", "")
        self._repo: Any = None
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        if use_sqlalchemy and _SqlWatchlistRepository is not None:
            try:
                self._repo = _SqlWatchlistRepository()
            except Exception:
                self._repo = None
        self.initialize()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def initialize(self) -> None:
        """Create storage tables when SQLAlchemy backend is not active."""
        if self._repo is not None:
            return
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(username, name)
            )
            """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watchlist_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(watchlist_id, ticker),
                FOREIGN KEY(watchlist_id) REFERENCES watchlists(id)
            )
            """)
        conn.commit()
        conn.close()

    def create_watchlist(self, data: WatchlistInput) -> int:
        """Create a watchlist (or reuse existing) and return its id."""
        if self._repo is not None:
            return int(self._repo.create_watchlist(username=data.username, name=data.name))
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
        if row is None:
            return 0
        return int(row[0])

    def delete_watchlist(self, watchlist_id: int, username: str) -> None:
        """Delete one watchlist and its items for the given user."""
        if self._repo is not None:
            self._repo.delete_watchlist(watchlist_id=watchlist_id, username=username)
            return
        conn = self._conn()
        conn.execute(
            "DELETE FROM watchlist_items WHERE watchlist_id IN (SELECT id FROM watchlists WHERE id = ? AND username = ?)",
            (watchlist_id, username),
        )
        conn.execute(
            "DELETE FROM watchlists WHERE id = ? AND username = ?", (watchlist_id, username)
        )
        conn.commit()
        conn.close()

    def add_ticker(self, watchlist_id: int, ticker: str) -> None:
        """Add a ticker symbol to a watchlist."""
        if self._repo is not None:
            self._repo.add_ticker(watchlist_id=watchlist_id, ticker=ticker)
            return
        stored_ticker = ticker.upper()
        if self._encryption_key:
            stored_ticker = encrypt_value(stored_ticker, self._encryption_key)
        conn = self._conn()
        conn.execute(
            "INSERT OR IGNORE INTO watchlist_items (watchlist_id, ticker, created_at) VALUES (?, ?, ?)",
            (watchlist_id, stored_ticker, datetime.now(UTC).isoformat()),
        )
        conn.commit()
        conn.close()

    def remove_ticker(self, watchlist_id: int, ticker: str) -> None:
        """Remove a ticker from a watchlist (plain or encrypted representation)."""
        if self._repo is not None:
            self._repo.remove_ticker(watchlist_id=watchlist_id, ticker=ticker)
            return
        conn = self._conn()
        plain = ticker.upper()
        encrypted = (
            encrypt_value(plain, self._encryption_key)
            if self._encryption_key
            else "__not_encrypted__"
        )
        conn.execute(
            "DELETE FROM watchlist_items WHERE watchlist_id = ? AND ticker = ?",
            (watchlist_id, plain),
        )
        conn.execute(
            "DELETE FROM watchlist_items WHERE watchlist_id = ? AND ticker = ?",
            (watchlist_id, encrypted),
        )
        conn.commit()
        conn.close()

    def list_watchlists(self, username: str) -> pd.DataFrame:
        """List all watchlists created by a user."""
        if self._repo is not None:
            return self._repo.list_watchlists(username=username)
        conn = self._conn()
        df = pd.read_sql_query(
            "SELECT id, name, created_at FROM watchlists WHERE username = ? ORDER BY created_at ASC",
            conn,
            params=(username,),
        )
        conn.close()
        return df

    def list_items(self, watchlist_id: int) -> pd.DataFrame:
        """List ticker items associated with one watchlist id."""
        if self._repo is not None:
            return self._repo.list_items(watchlist_id=watchlist_id)
        conn = self._conn()
        df = pd.read_sql_query(
            "SELECT ticker FROM watchlist_items WHERE watchlist_id = ? ORDER BY ticker ASC",
            conn,
            params=(watchlist_id,),
        )
        conn.close()
        if not df.empty and self._encryption_key:
            df["ticker"] = df["ticker"].apply(
                lambda value: (
                    decrypt_value(value, self._encryption_key)
                    if isinstance(value, str) and value.startswith("qv_enc_v")
                    else value
                )
            )
        return df
