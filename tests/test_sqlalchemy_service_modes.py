import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import services.alerts_service as alerts_module
import services.auth_service as auth_module
import services.portfolio_service as portfolio_module
import services.watchlist_service as watchlist_module
from services.alerts_service import AlertRule, AlertsService
from services.auth_service import AuthService
from services.portfolio_service import PortfolioService, PositionInput
from services.watchlist_service import WatchlistInput, WatchlistService


def test_portfolio_service_sqlalchemy_mode(monkeypatch) -> None:
    class FakeRepo:
        def __init__(self):
            self.positions = []

        def add_position(self, username, ticker, quantity, buy_price, buy_date):
            self.positions.append((username, ticker, quantity, buy_price, buy_date))
            return 1

        def remove_position(self, position_id, username):
            return None

        def list_positions(self, username):
            return pd.DataFrame(
                [
                    {
                        "id": 1,
                        "ticker": "AAPL",
                        "quantity": 2,
                        "buy_price": 100,
                        "buy_date": "2026-01-01",
                    }
                ]
            )

    monkeypatch.setattr(portfolio_module, "SqlPortfolioRepository", FakeRepo)
    svc = PortfolioService(use_sqlalchemy=True)
    svc.add_position(
        PositionInput(
            username="alice", ticker="AAPL", quantity=2, buy_price=100, buy_date="2026-01-01"
        )
    )
    listed = svc.list_positions("alice")
    assert not listed.empty


def test_watchlist_service_sqlalchemy_mode(monkeypatch) -> None:
    class FakeRepo:
        def create_watchlist(self, username, name):
            return 10

        def delete_watchlist(self, watchlist_id, username):
            return None

        def add_ticker(self, watchlist_id, ticker):
            return None

        def remove_ticker(self, watchlist_id, ticker):
            return None

        def list_watchlists(self, username):
            return pd.DataFrame([{"id": 10, "name": "Tech"}])

        def list_items(self, watchlist_id):
            return pd.DataFrame([{"ticker": "MSFT"}])

    monkeypatch.setattr(watchlist_module, "SqlWatchlistRepository", FakeRepo)
    svc = WatchlistService(use_sqlalchemy=True)
    watchlist_id = svc.create_watchlist(WatchlistInput(username="alice", name="Tech"))
    assert watchlist_id == 10
    assert not svc.list_items(10).empty


def test_alerts_service_sqlalchemy_mode(monkeypatch) -> None:
    class FakeRepo:
        def create_rule(self, username, ticker, alert_type, threshold, active):
            return 7

        def list_rules(self, username):
            return pd.DataFrame(
                [{"id": 7, "ticker": "AAPL", "alert_type": "new_high", "active": 1}]
            )

        def delete_rule(self, rule_id, username):
            return None

        def emit_alert(self, username, ticker, alert_type, message):
            return 99

        def list_history(self, username, limit=200):
            return pd.DataFrame([{"ticker": "AAPL", "alert_type": "new_high", "message": "x"}])

        def list_rule_owners(self):
            return ["alice"]

    monkeypatch.setattr(alerts_module, "SqlAlertsRepository", FakeRepo)
    svc = AlertsService(use_sqlalchemy=True)
    rule_id = svc.create_rule(AlertRule(username="alice", ticker="AAPL", alert_type="new_high"))
    assert rule_id == 7
    assert svc.emit_alert("alice", "AAPL", "new_high", "x") == 99
    assert svc.list_rule_owners() == ["alice"]


def test_auth_service_sqlalchemy_mode(monkeypatch) -> None:
    class FakeRepo:
        def __init__(self, database_url=None):
            self.users = {}

        def create_audit(self, **_kwargs):
            return None

        def get_locked_until(self, identifier):
            return None

        def get_failed_count(self, identifier):
            return 0

        def upsert_failed_login(self, identifier, failed_count, last_failed_at, locked_until):
            return None

        def clear_failed_attempts(self, identifier):
            return None

        def username_exists(self, username):
            return username in self.users

        def email_exists(self, email):
            return any(item["email"] == email.lower() for item in self.users.values())

        def create_user(self, username, email, first_name, last_name, role, password, created_at):
            self.users[username] = {"email": email.lower(), "password": password, "role": role}

        def get_password_by_identifier(self, identifier):
            for username, payload in self.users.items():
                if username == identifier or payload["email"] == identifier.lower():
                    return payload["password"]
            return None

        def upgrade_password_for_identifier(self, identifier, password):
            return None

        def get_username_by_identifier(self, identifier):
            for username, payload in self.users.items():
                if username == identifier or payload["email"] == identifier.lower():
                    return username
            return None

        def get_user_role(self, username):
            payload = self.users.get(username)
            return payload["role"] if payload else None

        def set_user_role(self, username, role):
            if username not in self.users:
                return False
            self.users[username]["role"] = role
            return True

        def list_users(self):
            return [
                (username, payload["email"], payload["role"])
                for username, payload in self.users.items()
            ]

        def create_session(self, session_id, username, login_time, expires_at, invalidate_existing):
            return None

        def get_session_expires_at(self, session_id):
            return None

        def get_session_username_and_expiry(self, session_id):
            return (None, None)

        def invalidate_session(self, session_id):
            return None

        def cleanup_expired_sessions(self, now):
            return 0

        def upsert_user(self, username, email, first_name, last_name, role, password, created_at):
            self.users[username] = {"email": email.lower(), "password": password, "role": role}

    monkeypatch.setattr(auth_module, "SqlAuthRepository", FakeRepo)
    svc = AuthService(use_sqlalchemy=True)
    ok, err = svc.register_user("alice", "alice@example.com", "A", "L", "Strong*Pass1")
    assert ok is True
    assert err is None
    assert svc.authenticate_user("alice@example.com", "Strong*Pass1") is True
