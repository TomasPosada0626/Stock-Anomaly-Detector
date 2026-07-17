from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class StrategyProposal:
    strategy_name: str
    created_by: str
    rationale: str


class StrategyGovernanceService:
    def __init__(self, db_path: str = "storage/governance.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _initialize(self) -> None:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS strategy_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                created_by TEXT NOT NULL,
                rationale TEXT NOT NULL,
                status TEXT NOT NULL,
                approved_by TEXT,
                decision_at TEXT,
                created_at TEXT NOT NULL
            )
            """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_strategy_proposals_status_created_at ON strategy_proposals (status, created_at)"
        )
        conn.commit()
        conn.close()

    def submit_proposal(self, proposal: StrategyProposal) -> int:
        strategy_name = proposal.strategy_name.strip()
        created_by = proposal.created_by.strip()
        rationale = proposal.rationale.strip()
        if not strategy_name or not created_by or not rationale:
            raise ValueError("strategy_name, created_by and rationale are required")

        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO strategy_proposals (strategy_name, created_by, rationale, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                strategy_name,
                created_by,
                rationale,
                "PENDING",
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        row_id = int(cur.lastrowid)
        conn.close()
        return row_id

    def approve_proposal(self, proposal_id: int, approved_by: str) -> bool:
        approver = approved_by.strip()
        if not approver:
            raise ValueError("approved_by is required")

        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE strategy_proposals
            SET status = ?, approved_by = ?, decision_at = ?
            WHERE id = ? AND status = ?
            """,
            (
                "APPROVED",
                approver,
                datetime.now(UTC).isoformat(),
                int(proposal_id),
                "PENDING",
            ),
        )
        conn.commit()
        updated = cur.rowcount > 0
        conn.close()
        return bool(updated)

    def reject_proposal(self, proposal_id: int, approved_by: str) -> bool:
        approver = approved_by.strip()
        if not approver:
            raise ValueError("approved_by is required")

        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE strategy_proposals
            SET status = ?, approved_by = ?, decision_at = ?
            WHERE id = ? AND status = ?
            """,
            (
                "REJECTED",
                approver,
                datetime.now(UTC).isoformat(),
                int(proposal_id),
                "PENDING",
            ),
        )
        conn.commit()
        updated = cur.rowcount > 0
        conn.close()
        return bool(updated)

    def list_proposals(self, status: str | None = None, limit: int = 200) -> pd.DataFrame:
        conn = self._conn()
        if status and status.strip():
            frame = pd.read_sql_query(
                """
                SELECT id, strategy_name, created_by, rationale, status, approved_by, decision_at, created_at
                FROM strategy_proposals
                WHERE status = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                conn,
                params=(status.strip().upper(), max(1, int(limit))),
            )
        else:
            frame = pd.read_sql_query(
                """
                SELECT id, strategy_name, created_by, rationale, status, approved_by, decision_at, created_at
                FROM strategy_proposals
                ORDER BY id DESC
                LIMIT ?
                """,
                conn,
                params=(max(1, int(limit)),),
            )
        conn.close()
        return frame
