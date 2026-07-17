from __future__ import annotations

import os
import sqlite3
from dataclasses import asdict, dataclass

from config import APP_LOG_DIR, DATABASE_URL, USERS_DB_PATH
from repositories.sqlalchemy_adapter import SqlAlchemyAdapter


@dataclass(frozen=True)
class ComponentStatus:
    name: str
    ok: bool
    message: str


class HealthService:
    def __init__(self) -> None:
        self.sql_adapter = SqlAlchemyAdapter(DATABASE_URL)

    def _check_users_db(self) -> ComponentStatus:
        try:
            conn = sqlite3.connect(USERS_DB_PATH)
            conn.execute("SELECT 1")
            conn.close()
            return ComponentStatus(name="users_db", ok=True, message="ok")
        except Exception as exc:
            return ComponentStatus(name="users_db", ok=False, message=str(exc))

    def _check_logs_dir(self) -> ComponentStatus:
        try:
            os.makedirs(APP_LOG_DIR, exist_ok=True)
            writable = os.access(APP_LOG_DIR, os.W_OK)
            if writable:
                return ComponentStatus(name="logs_dir", ok=True, message="ok")
            return ComponentStatus(name="logs_dir", ok=False, message="not writable")
        except Exception as exc:
            return ComponentStatus(name="logs_dir", ok=False, message=str(exc))

    def _check_sqlalchemy(self) -> ComponentStatus:
        status = self.sql_adapter.ping()
        return ComponentStatus(
            name="sqlalchemy",
            ok=status.ok,
            message=f"enabled={status.enabled} dialect={status.dialect} msg={status.message}",
        )

    def run_checks(self) -> dict[str, object]:
        checks = [self._check_users_db(), self._check_logs_dir(), self._check_sqlalchemy()]
        overall_ok = all(item.ok for item in checks)
        return {
            "status": "ok" if overall_ok else "degraded",
            "checks": [asdict(item) for item in checks],
        }
