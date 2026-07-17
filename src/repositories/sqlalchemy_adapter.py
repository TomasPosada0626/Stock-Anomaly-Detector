from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import DATABASE_URL
from services.observability import get_logger

_sqlalchemy_text: Any

try:
    from sqlalchemy import create_engine
    from sqlalchemy import text as _sqlalchemy_text_imported
    from sqlalchemy.engine import Engine
    _sqlalchemy_text = _sqlalchemy_text_imported
except Exception:  # pragma: no cover - optional dependency
    Engine = Any
    create_engine = None
    _sqlalchemy_text = None


logger = get_logger("sqlalchemy_adapter")


@dataclass(frozen=True)
class SqlHealth:
    enabled: bool
    available: bool
    dialect: str
    ok: bool
    message: str


class SqlAlchemyAdapter:
    def __init__(self, database_url: str = DATABASE_URL) -> None:
        self.database_url = database_url
        self._engine: Engine | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.database_url and create_engine is not None)

    def get_engine(self) -> Engine | None:
        if not self.enabled:
            return None
        if self._engine is None:
            self._engine = create_engine(self.database_url, pool_pre_ping=True, future=True)
        return self._engine

    def ping(self) -> SqlHealth:
        if not self.enabled:
            return SqlHealth(
                enabled=False,
                available=create_engine is not None,
                dialect="none",
                ok=False,
                message="SQLAlchemy adapter disabled or dependency missing",
            )

        engine = self.get_engine()
        if engine is None:
            return SqlHealth(
                enabled=False,
                available=False,
                dialect="none",
                ok=False,
                message="Engine unavailable",
            )
        try:
            with engine.connect() as conn:
                if _sqlalchemy_text is None:
                    raise RuntimeError("sqlalchemy text helper unavailable")
                conn.execute(_sqlalchemy_text("SELECT 1"))
            return SqlHealth(
                enabled=True,
                available=True,
                dialect=engine.dialect.name,
                ok=True,
                message="ok",
            )
        except Exception as exc:
            logger.warning("sqlalchemy_ping_failed error=%s", str(exc))
            return SqlHealth(
                enabled=True,
                available=True,
                dialect=getattr(engine.dialect, "name", "unknown"),
                ok=False,
                message=str(exc),
            )
