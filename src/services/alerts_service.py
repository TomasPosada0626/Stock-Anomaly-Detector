from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from config import USE_SQLALCHEMY_REPOSITORIES

try:
    from repositories.sqlalchemy_domain_repositories import SqlAlertsRepository
except Exception:  # pragma: no cover - optional dependency
    SqlAlertsRepository = None  # type: ignore[assignment]


@dataclass(frozen=True)
class AlertRule:
    username: str
    ticker: str
    alert_type: str
    threshold: float | None = None
    active: bool = True


class AlertsService:
    def __init__(self, db_path: str = "storage/quantvision.db", use_sqlalchemy: bool = USE_SQLALCHEMY_REPOSITORIES) -> None:
        self.db_path = db_path
        self._repo = None
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        if use_sqlalchemy and SqlAlertsRepository is not None:
            try:
                self._repo = SqlAlertsRepository()
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
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ticker TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                threshold REAL,
                active INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ticker TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                triggered_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    def create_rule(self, rule: AlertRule) -> int:
        if self._repo is not None:
            return self._repo.create_rule(
                username=rule.username,
                ticker=rule.ticker,
                alert_type=rule.alert_type,
                threshold=rule.threshold,
                active=rule.active,
            )
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO alert_rules (username, ticker, alert_type, threshold, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rule.username,
                rule.ticker.upper(),
                rule.alert_type,
                rule.threshold,
                int(rule.active),
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        row_id = int(cur.lastrowid)
        conn.close()
        return row_id

    def list_rules(self, username: str) -> pd.DataFrame:
        if self._repo is not None:
            return self._repo.list_rules(username=username)
        conn = self._conn()
        df = pd.read_sql_query(
            "SELECT id, ticker, alert_type, threshold, active FROM alert_rules WHERE username = ? ORDER BY id DESC",
            conn,
            params=(username,),
        )
        conn.close()
        return df

    def delete_rule(self, rule_id: int, username: str) -> None:
        if self._repo is not None:
            self._repo.delete_rule(rule_id=rule_id, username=username)
            return
        conn = self._conn()
        conn.execute("DELETE FROM alert_rules WHERE id = ? AND username = ?", (rule_id, username))
        conn.commit()
        conn.close()

    def emit_alert(self, username: str, ticker: str, alert_type: str, message: str) -> int:
        if self._repo is not None:
            return self._repo.emit_alert(
                username=username,
                ticker=ticker,
                alert_type=alert_type,
                message=message,
            )
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO alert_history (username, ticker, alert_type, message, triggered_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, ticker.upper(), alert_type, message, datetime.now(UTC).isoformat()),
        )
        conn.commit()
        row_id = int(cur.lastrowid)
        conn.close()
        return row_id

    def list_history(self, username: str, limit: int = 200) -> pd.DataFrame:
        if self._repo is not None:
            return self._repo.list_history(username=username, limit=limit)
        conn = self._conn()
        df = pd.read_sql_query(
            "SELECT ticker, alert_type, message, triggered_at FROM alert_history WHERE username = ? ORDER BY id DESC LIMIT ?",
            conn,
            params=(username, int(limit)),
        )
        conn.close()
        return df

    def list_rule_owners(self) -> list[str]:
        if self._repo is not None:
            return self._repo.list_rule_owners()

        conn = self._conn()
        rows = conn.execute("SELECT DISTINCT username FROM alert_rules WHERE username != ''").fetchall()
        conn.close()
        return sorted(str(row[0]) for row in rows if row and row[0])
