from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


class ExperimentationService:
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
            CREATE TABLE IF NOT EXISTS ab_experiments (
                name TEXT PRIMARY KEY,
                feature TEXT NOT NULL,
                variants TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ab_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_name TEXT NOT NULL,
                username TEXT NOT NULL,
                variant TEXT NOT NULL,
                exposed INTEGER NOT NULL,
                converted INTEGER NOT NULL,
                assigned_at TEXT NOT NULL,
                converted_at TEXT,
                UNIQUE(experiment_name, username),
                FOREIGN KEY(experiment_name) REFERENCES ab_experiments(name)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ab_assignments_experiment_variant ON ab_assignments (experiment_name, variant)"
        )
        conn.commit()
        conn.close()

    def create_experiment(
        self,
        name: str,
        feature: str,
        variants: list[str],
        hypothesis: str,
        status: str = "active",
    ) -> None:
        clean_name = name.strip()
        clean_feature = feature.strip()
        clean_variants = [item.strip() for item in variants if item.strip()]
        clean_hypothesis = hypothesis.strip()
        if not clean_name:
            raise ValueError("experiment name is required")
        if len(clean_variants) < 2:
            raise ValueError("at least two variants are required")

        conn = self._conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO ab_experiments (name, feature, variants, hypothesis, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                clean_name,
                clean_feature,
                json.dumps(clean_variants),
                clean_hypothesis,
                status,
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    def list_experiments(self, status: str | None = None) -> pd.DataFrame:
        conn = self._conn()
        if status:
            frame = pd.read_sql_query(
                "SELECT name, feature, variants, hypothesis, status, created_at FROM ab_experiments WHERE status = ? ORDER BY created_at DESC",
                conn,
                params=(status,),
            )
        else:
            frame = pd.read_sql_query(
                "SELECT name, feature, variants, hypothesis, status, created_at FROM ab_experiments ORDER BY created_at DESC",
                conn,
            )
        conn.close()
        if not frame.empty:
            frame["variants"] = frame["variants"].apply(json.loads)
        return frame

    def assign_variant(self, experiment_name: str, username: str) -> str:
        conn = self._conn()
        row = conn.execute(
            "SELECT variants, status FROM ab_experiments WHERE name = ?",
            (experiment_name,),
        ).fetchone()
        if row is None:
            conn.close()
            raise ValueError("experiment not found")

        variants = json.loads(str(row[0]))
        status = str(row[1])
        if status != "active":
            conn.close()
            raise ValueError("experiment is not active")

        seed = f"{experiment_name}|{username}".encode("utf-8")
        digest = hashlib.sha256(seed).hexdigest()
        index = int(digest[:8], 16) % len(variants)
        variant = str(variants[index])

        conn.execute(
            """
            INSERT OR IGNORE INTO ab_assignments
                (experiment_name, username, variant, exposed, converted, assigned_at, converted_at)
            VALUES (?, ?, ?, 1, 0, ?, NULL)
            """,
            (experiment_name, username, variant, datetime.now(UTC).isoformat()),
        )
        conn.commit()
        conn.close()
        return variant

    def track_conversion(self, experiment_name: str, username: str) -> None:
        conn = self._conn()
        conn.execute(
            """
            UPDATE ab_assignments
            SET converted = 1,
                converted_at = ?
            WHERE experiment_name = ? AND username = ?
            """,
            (datetime.now(UTC).isoformat(), experiment_name, username),
        )
        conn.commit()
        conn.close()

    def summary(self, experiment_name: str) -> pd.DataFrame:
        conn = self._conn()
        frame = pd.read_sql_query(
            """
            SELECT
                variant,
                COUNT(*) AS exposures,
                SUM(converted) AS conversions,
                CASE
                    WHEN COUNT(*) = 0 THEN 0.0
                    ELSE CAST(SUM(converted) AS REAL) / COUNT(*)
                END AS conversion_rate
            FROM ab_assignments
            WHERE experiment_name = ?
            GROUP BY variant
            ORDER BY variant ASC
            """,
            conn,
            params=(experiment_name,),
        )
        conn.close()
        return frame
