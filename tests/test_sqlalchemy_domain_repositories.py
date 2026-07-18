import os
import sys
from datetime import UTC, datetime, timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from repositories import sqlalchemy_domain_repositories as repo_module


@pytest.mark.skipif(repo_module.create_engine is None, reason="SQLAlchemy not installed")
def test_sql_portfolio_repository_crud(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'portfolio.db'}"
    repo = repo_module.SqlPortfolioRepository(database_url=db_url)
    try:
        alice_older = repo.add_position("alice", "aapl", 2, 100.0, "2024-01-01")
        alice_newer = repo.add_position("alice", "msft", 1, 200.0, "2025-01-01")
        bob_id = repo.add_position("bob", "nvda", 3, 90.0, "2025-02-01")

        alice_positions = repo.list_positions("alice")
        assert len(alice_positions) == 2
        assert alice_positions.iloc[0]["id"] == alice_older
        assert alice_positions.iloc[1]["id"] == alice_newer
        assert alice_positions.iloc[0]["ticker"] == "AAPL"

        repo.remove_position(position_id=bob_id, username="alice")
        assert len(repo.list_positions("bob")) == 1

        repo.remove_position(position_id=bob_id, username="bob")
        assert repo.list_positions("bob").empty
    finally:
        repo.engine.dispose()


@pytest.mark.skipif(repo_module.create_engine is None, reason="SQLAlchemy not installed")
def test_sql_watchlist_repository_crud(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'watchlists.db'}"
    repo = repo_module.SqlWatchlistRepository(database_url=db_url)
    try:
        watchlist_id = repo.create_watchlist("alice", " Tech ")
        watchlist_same = repo.create_watchlist("alice", "Tech")
        assert watchlist_id == watchlist_same

        repo.add_ticker(watchlist_id, "aapl")
        repo.add_ticker(watchlist_id, "msft")
        repo.add_ticker(watchlist_id, "AAPL")

        items = repo.list_items(watchlist_id)
        assert len(items) == 2
        assert items["ticker"].tolist() == ["AAPL", "MSFT"]

        watchlists = repo.list_watchlists("alice")
        assert len(watchlists) == 1
        assert watchlists.iloc[0]["name"] == "Tech"

        repo.remove_ticker(watchlist_id, "msft")
        items_after_remove = repo.list_items(watchlist_id)
        assert items_after_remove["ticker"].tolist() == ["AAPL"]

        repo.delete_watchlist(watchlist_id=watchlist_id, username="alice")
        assert repo.list_watchlists("alice").empty
        assert repo.list_items(watchlist_id).empty
    finally:
        repo.engine.dispose()


@pytest.mark.skipif(repo_module.create_engine is None, reason="SQLAlchemy not installed")
def test_sql_alerts_repository_crud_and_owner_listing(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'alerts.db'}"
    repo = repo_module.SqlAlertsRepository(database_url=db_url)
    try:
        alice_rule = repo.create_rule("alice", "aapl", "new_high", None, True)
        bob_rule = repo.create_rule("bob", "msft", "price_change_pct", 4.0, False)

        alice_rules = repo.list_rules("alice")
        assert len(alice_rules) == 1
        assert int(alice_rules.iloc[0]["id"]) == alice_rule

        all_rules = repo.list_rules("")
        assert len(all_rules) == 2
        assert "username" in all_rules.columns

        alert_id = repo.emit_alert("alice", "aapl", "new_high", "breakout")
        assert alert_id > 0

        history = repo.list_history("alice", limit=10)
        assert len(history) == 1
        assert history.iloc[0]["ticker"] == "AAPL"

        owners = repo.list_rule_owners()
        assert owners == ["alice", "bob"]

        repo.delete_rule(rule_id=bob_rule, username="alice")
        assert len(repo.list_rules("bob")) == 1

        repo.delete_rule(rule_id=bob_rule, username="bob")
        assert repo.list_rules("bob").empty
    finally:
        repo.engine.dispose()


@pytest.mark.skipif(repo_module.create_engine is None, reason="SQLAlchemy not installed")
def test_sql_auth_repository_crud_and_session_flow(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'auth.db'}"
    repo = repo_module.SqlAuthRepository(database_url=db_url)
    try:
        created_at = datetime.now(UTC)
        repo.create_user(
            username="tomas",
            email="tomas@example.com",
            first_name="Tomas",
            last_name="Posada",
            role="ADMIN",
            password="hashed",
            created_at=created_at,
        )
        assert repo.username_exists("tomas") is True
        assert repo.email_exists("tomas@example.com") is True
        assert repo.get_username_by_identifier("tomas@example.com") == "tomas"
        assert repo.get_user_role("tomas") == "ADMIN"

        repo.create_session(
            session_id="abc123",
            username="tomas",
            login_time=created_at,
            expires_at=created_at + timedelta(minutes=60),
            invalidate_existing=True,
        )
        session_user, expires_at = repo.get_session_username_and_expiry("abc123")
        assert session_user == "tomas"
        assert expires_at is not None

        repo.upsert_failed_login("tomas@example.com", 2, created_at, None)
        assert repo.get_failed_count("tomas@example.com") == 2
        repo.clear_failed_attempts("tomas@example.com")
        assert repo.get_failed_count("tomas@example.com") == 0
    finally:
        repo.engine.dispose()
