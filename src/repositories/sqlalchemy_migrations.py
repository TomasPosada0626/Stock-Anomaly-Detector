from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

try:
    from sqlalchemy import text
except Exception:  # pragma: no cover - optional dependency
    text = None

LATEST_SCHEMA_VERSION = 3


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _bootstrap_migrations_table(engine: Any) -> None:
    assert text is not None
    with engine.begin() as conn:
        conn.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """))


def _get_current_version(engine: Any) -> int:
    assert text is not None
    with engine.begin() as conn:
        row = conn.execute(text("SELECT MAX(version) FROM schema_migrations")).first()
    return int(row[0]) if row and row[0] is not None else 0


def _migration_1_create_domain_tables(engine: Any) -> None:
    assert text is not None
    statements = [
        """
        CREATE TABLE IF NOT EXISTS portfolio_positions (
            id INTEGER PRIMARY KEY,
            username VARCHAR(120) NOT NULL,
            ticker VARCHAR(20) NOT NULL,
            quantity FLOAT NOT NULL,
            buy_price FLOAT NOT NULL,
            buy_date VARCHAR(40) NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_portfolio_positions_username ON portfolio_positions (username)",
        """
        CREATE TABLE IF NOT EXISTS watchlists (
            id INTEGER PRIMARY KEY,
            username VARCHAR(120) NOT NULL,
            name VARCHAR(120) NOT NULL,
            created_at TIMESTAMP NOT NULL,
            CONSTRAINT uq_watchlists_username_name UNIQUE (username, name)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_watchlists_username ON watchlists (username)",
        """
        CREATE TABLE IF NOT EXISTS watchlist_items (
            id INTEGER PRIMARY KEY,
            watchlist_id INTEGER NOT NULL,
            ticker VARCHAR(20) NOT NULL,
            created_at TIMESTAMP NOT NULL,
            CONSTRAINT uq_watchlist_items_pair UNIQUE (watchlist_id, ticker)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_watchlist_items_watchlist_id ON watchlist_items (watchlist_id)",
        """
        CREATE TABLE IF NOT EXISTS alert_rules (
            id INTEGER PRIMARY KEY,
            username VARCHAR(120) NOT NULL,
            ticker VARCHAR(20) NOT NULL,
            alert_type VARCHAR(60) NOT NULL,
            threshold FLOAT NULL,
            active BOOLEAN NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_alert_rules_username ON alert_rules (username)",
        """
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY,
            username VARCHAR(120) NOT NULL,
            ticker VARCHAR(20) NOT NULL,
            alert_type VARCHAR(60) NOT NULL,
            message VARCHAR(400) NOT NULL,
            triggered_at TIMESTAMP NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_alert_history_username ON alert_history (username)",
    ]

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        conn.execute(
            text(
                "INSERT INTO schema_migrations (version, description, applied_at) VALUES (:version, :description, :applied_at)"
            ),
            {
                "version": 1,
                "description": "create_domain_tables",
                "applied_at": _utcnow_iso(),
            },
        )


def _migration_2_add_performance_indexes(engine: Any) -> None:
    assert text is not None
    statements = [
        "CREATE INDEX IF NOT EXISTS idx_portfolio_positions_user_ticker_date ON portfolio_positions (username, ticker, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_watchlists_user_created_at ON watchlists (username, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_watchlist_items_ticker_created_at ON watchlist_items (ticker, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_alert_rules_user_ticker_active ON alert_rules (username, ticker, active)",
        "CREATE INDEX IF NOT EXISTS idx_alert_rules_ticker_created_at ON alert_rules (ticker, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_alert_history_user_triggered_at ON alert_history (username, triggered_at)",
        "CREATE INDEX IF NOT EXISTS idx_alert_history_ticker_triggered_at ON alert_history (ticker, triggered_at)",
    ]

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        conn.execute(
            text(
                "INSERT INTO schema_migrations (version, description, applied_at) VALUES (:version, :description, :applied_at)"
            ),
            {
                "version": 2,
                "description": "add_performance_indexes",
                "applied_at": _utcnow_iso(),
            },
        )


def _migration_3_add_auth_tables(engine: Any) -> None:
    assert text is not None
    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            username VARCHAR(120) PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            first_name VARCHAR(120) NOT NULL,
            last_name VARCHAR(120) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'ANALYST',
            password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)",
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id VARCHAR(80) PRIMARY KEY,
            username VARCHAR(120),
            login_time TIMESTAMP,
            expires_at TIMESTAMP
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions (username)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at)",
        """
        CREATE TABLE IF NOT EXISTS failed_logins (
            identifier VARCHAR(255) PRIMARY KEY,
            failed_count INTEGER NOT NULL,
            last_failed_at TIMESTAMP NOT NULL,
            locked_until TIMESTAMP NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS auth_audit (
            id INTEGER PRIMARY KEY,
            event_type VARCHAR(60) NOT NULL,
            identifier VARCHAR(255),
            success BOOLEAN NOT NULL,
            message VARCHAR(400),
            created_at TIMESTAMP NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_auth_audit_identifier_created_at ON auth_audit (identifier, created_at)",
    ]

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        conn.execute(
            text(
                "INSERT INTO schema_migrations (version, description, applied_at) VALUES (:version, :description, :applied_at)"
            ),
            {
                "version": 3,
                "description": "add_auth_tables",
                "applied_at": _utcnow_iso(),
            },
        )


def explain_query_plan(engine: Any, query: str) -> list[tuple[object, ...]]:
    """Return a portable query-plan snapshot for diagnostics in development environments."""
    if text is None:
        raise RuntimeError("SQLAlchemy dependency not available")

    with engine.begin() as conn:
        result = conn.execute(text(f"EXPLAIN QUERY PLAN {query}"))
        return [tuple(row) for row in result.fetchall()]


def ensure_domain_schema(engine: Any, target_version: int = LATEST_SCHEMA_VERSION) -> int:
    if text is None:
        raise RuntimeError("SQLAlchemy dependency not available")

    _bootstrap_migrations_table(engine)
    current = _get_current_version(engine)

    if current < 1 and target_version >= 1:
        _migration_1_create_domain_tables(engine)
        current = 1

    if current < 2 and target_version >= 2:
        _migration_2_add_performance_indexes(engine)
        current = 2

    if current < 3 and target_version >= 3:
        _migration_3_add_auth_tables(engine)
        current = 3

    return current
