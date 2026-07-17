from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class AnalyticsEvent:
    username: str
    feature: str
    event_name: str
    metadata: str = ""


class EventTracker:
    def __init__(self, db_path: str = "storage/analytics.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _initialize(self) -> None:
        conn = self._conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                feature TEXT NOT NULL,
                event_name TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_events_feature_created_at ON analytics_events (feature, created_at)"
        )
        conn.commit()
        conn.close()

    def track(self, event: AnalyticsEvent) -> int:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO analytics_events (username, feature, event_name, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event.username,
                event.feature,
                event.event_name,
                event.metadata,
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        row_id = int(cur.lastrowid)
        conn.close()
        return row_id

    def list_events(self, limit: int = 500) -> pd.DataFrame:
        conn = self._conn()
        frame = pd.read_sql_query(
            "SELECT username, feature, event_name, metadata, created_at FROM analytics_events ORDER BY id DESC LIMIT ?",
            conn,
            params=(max(1, int(limit)),),
        )
        conn.close()
        return frame

    def top_features(self, limit: int = 10) -> pd.DataFrame:
        conn = self._conn()
        frame = pd.read_sql_query(
            """
            SELECT feature, COUNT(*) AS events
            FROM analytics_events
            GROUP BY feature
            ORDER BY events DESC, feature ASC
            LIMIT ?
            """,
            conn,
            params=(max(1, int(limit)),),
        )
        conn.close()
        return frame

    def funnel(self) -> dict[str, int]:
        conn = self._conn()
        rows = conn.execute(
            """
            SELECT event_name, COUNT(*)
            FROM analytics_events
            WHERE event_name IN ('login_success', 'load_market_data', 'run_anomaly_methods', 'export_report')
            GROUP BY event_name
            """
        ).fetchall()
        conn.close()

        base = {
            "login_success": 0,
            "load_market_data": 0,
            "run_anomaly_methods": 0,
            "export_report": 0,
        }
        for event_name, count in rows:
            base[str(event_name)] = int(count)
        return base
