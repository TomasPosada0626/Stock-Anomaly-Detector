import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from repositories import sqlalchemy_migrations as migrations


@pytest.mark.skipif(migrations.text is None, reason="SQLAlchemy not installed")
def test_ensure_domain_schema_creates_version_and_tables(tmp_path) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(f"sqlite:///{tmp_path / 'migrations.db'}", future=True)
    try:
        version = migrations.ensure_domain_schema(engine)
        assert version == migrations.LATEST_SCHEMA_VERSION

        with engine.begin() as conn:
            migration_version = conn.execute(
                text("SELECT MAX(version) FROM schema_migrations")
            ).scalar()
            assert int(migration_version) == migrations.LATEST_SCHEMA_VERSION

            positions_exists = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='portfolio_positions'"
                )
            ).first()
            rules_exists = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='alert_rules'")
            ).first()

        assert positions_exists is not None
        assert rules_exists is not None
    finally:
        engine.dispose()


@pytest.mark.skipif(migrations.text is None, reason="SQLAlchemy not installed")
def test_ensure_domain_schema_is_idempotent(tmp_path) -> None:
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{tmp_path / 'migrations_idempotent.db'}", future=True)
    try:
        first = migrations.ensure_domain_schema(engine)
        second = migrations.ensure_domain_schema(engine)
        assert first == second == migrations.LATEST_SCHEMA_VERSION
    finally:
        engine.dispose()


@pytest.mark.skipif(migrations.text is None, reason="SQLAlchemy not installed")
def test_migration_v2_indexes_and_explain_query_plan(tmp_path) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(f"sqlite:///{tmp_path / 'migrations_indexes.db'}", future=True)
    try:
        version = migrations.ensure_domain_schema(engine)
        assert version >= 2

        with engine.begin() as conn:
            idx_row = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_alert_history_user_triggered_at'"
                )
            ).first()

        assert idx_row is not None

        plan = migrations.explain_query_plan(
            engine,
            "SELECT * FROM alert_history WHERE username = 'alice' ORDER BY triggered_at DESC",
        )
        assert isinstance(plan, list)
    finally:
        engine.dispose()
