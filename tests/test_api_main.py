import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import api.main as api_main
from api.main import create_app, parse_prices


def test_parse_prices_skips_invalid_tokens() -> None:
    prices = parse_prices("aapl:100.5, badtoken, msft:abc, nvda:140")
    assert prices == {"AAPL": 100.5, "NVDA": 140.0}


def test_parse_prices_empty_input() -> None:
    assert parse_prices("") == {}


def test_create_app_or_runtime_error() -> None:
    try:
        app = create_app()
        # FastAPI branch
        assert app is not None
    except RuntimeError as exc:
        # Optional dependency branch
        assert "FastAPI is not installed" in str(exc)


def test_create_app_with_fake_fastapi_branch(monkeypatch) -> None:
    class FakeApp:
        def __init__(self, title: str, version: str):
            self.title = title
            self.version = version
            self.routes = {}

        def get(self, path: str):
            def decorator(func):
                self.routes[path] = func
                return func

            return decorator

        def post(self, path: str):
            def decorator(func):
                self.routes[f"POST {path}"] = func
                return func

            return decorator

        def delete(self, path: str):
            def decorator(func):
                self.routes[f"DELETE {path}"] = func
                return func

            return decorator

    class FakeAuth:
        def get_user_role(self, username: str) -> str:
            return "ANALYST"

        def can_access_module(self, username: str, module_name: str) -> bool:
            return True

        def validate_session_owner(self, session_id: str, username: str) -> bool:
            return session_id == "valid-session" and username == "alice"

        def authenticate_user_with_reason(self, identifier: str, password: str):
            if identifier == "alice" and password == "Strong*Pass1":
                return True, ""
            return False, "Invalid username/email or password."

        def get_username_by_identifier(self, identifier: str):
            return "alice" if identifier == "alice" else None

        def create_session(self, username: str) -> str:
            return "valid-session"

        def is_session_valid(self, session_id: str) -> bool:
            return session_id == "valid-session"

        def invalidate_session(self, session_id: str):
            return None

    class FakePortfolio:
        def compute_portfolio_metrics(self, username: str, latest_prices):
            return {"Invested Capital": 100.0, "Current Value": 110.0, "PnL": 10.0, "ROI %": 10.0}

        def list_positions(self, username: str):
            return pd.DataFrame([{"ticker": "AAPL", "quantity": 2, "buy_price": 95}])

        def add_position(self, data):
            return 99

        def remove_position(self, position_id: int, username: str):
            return None

    class FakeAlerts:
        def list_history(self, username: str, limit: int = 100):
            return pd.DataFrame([{"ticker": "AAPL", "alert_type": "rsi_gt_70", "message": "x"}])

        def list_rules(self, username: str):
            return pd.DataFrame(
                [{"id": 5, "ticker": "AAPL", "alert_type": "rsi_gt_70", "active": 1}]
            )

        def create_rule(self, rule):
            return 5

        def delete_rule(self, rule_id: int, username: str):
            return None

    class FakeWatchlists:
        def list_watchlists(self, username: str):
            return pd.DataFrame([{"id": 1, "name": "Tech", "created_at": "2026-01-01"}])

        def list_items(self, watchlist_id: int):
            return pd.DataFrame([{"ticker": "AAPL"}, {"ticker": "MSFT"}])

        def create_watchlist(self, data):
            return 1

        def delete_watchlist(self, watchlist_id: int, username: str):
            return None

        def add_ticker(self, watchlist_id: int, ticker: str):
            return None

        def remove_ticker(self, watchlist_id: int, ticker: str):
            return None

    class FakeReports:
        def build_portfolio_report(self, title: str, portfolio_metrics, positions):
            return b"pdf"

    class FakeBacktesting:
        def run_rule_based_strategy(self, df, rules):
            return {"Return %": 1.0, "Trade Log": [{"Action": "BUY"}]}

    class FakeHTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    monkeypatch.setattr(api_main, "FastAPI", FakeApp)
    monkeypatch.setattr(api_main, "HTTPException", FakeHTTPException)
    monkeypatch.setattr(
        api_main,
        "get_ticker_data",
        lambda ticker, start_date, end_date: (
            pd.DataFrame(
                {
                    "Close": [100, 101, 102],
                    "Open": [99, 100, 101],
                    "High": [101, 102, 103],
                    "Low": [98, 99, 100],
                    "Volume": [1000, 1100, 900],
                },
                index=pd.date_range("2026-01-01", periods=3, freq="D"),
            ),
            False,
            None,
        ),
    )

    app = api_main.create_app(
        FakeAuth(),
        FakePortfolio(),
        FakeAlerts(),
        FakeWatchlists(),
        FakeReports(),
        FakeBacktesting(),
    )
    assert app.title == "QuantVision API"

    health = app.routes["/health"]()
    assert health["status"] == "ok"

    denied_role = False
    try:
        app.routes["/users/{username}/role"]("alice")
    except FakeHTTPException as exc:
        denied_role = True
        assert exc.status_code == 401
    assert denied_role is True

    role = app.routes["/users/{username}/role"]("alice", session_id="valid-session")
    assert role["role"] == "ANALYST"

    login_payload = type("LoginPayload", (), {"identifier": "alice", "password": "Strong*Pass1"})()
    login_response = app.routes["POST /auth/login"](payload=login_payload)
    assert login_response["session_id"] == "valid-session"

    logout_response = app.routes["POST /auth/logout"](session_id="valid-session")
    assert logout_response["logged_out"] is True

    summary = app.routes["/users/{username}/portfolio/summary"](
        "alice", prices="AAPL:100", session_id="valid-session"
    )
    assert summary["PnL"] == 10.0

    history = app.routes["/users/{username}/alerts/history"](
        "alice", limit=10, session_id="valid-session"
    )
    assert len(history) == 1

    watchlists = app.routes["/users/{username}/watchlists"]("alice", session_id="valid-session")
    assert len(watchlists) == 1

    items = app.routes["/users/{username}/watchlists/{watchlist_id}/items"](
        "alice", watchlist_id=1, session_id="valid-session"
    )
    assert len(items) == 2

    indicators = app.routes["/analytics/{ticker}/indicators"]("aapl")
    assert indicators["ticker"] == "AAPL"

    anomalies = app.routes["/analytics/{ticker}/anomalies"]("aapl")
    assert "zscore_count" in anomalies

    backtest = app.routes["/analytics/{ticker}/backtest"]("aapl")
    assert "Return %" in backtest

    report = app.routes["/users/{username}/reports/portfolio"](
        "alice", prices="AAPL:100", session_id="valid-session"
    )
    assert report["pdf_bytes"] == 3

    positions = app.routes["/users/{username}/portfolio/positions"](
        "alice", session_id="valid-session"
    )
    assert len(positions) == 1

    payload_position = type(
        "PositionPayload",
        (),
        {"ticker": "AAPL", "quantity": 1.0, "buy_price": 100.0, "buy_date": "2026-01-01"},
    )()
    created_position = app.routes["POST /users/{username}/portfolio/positions"](
        "alice", payload=payload_position, session_id="valid-session"
    )
    assert created_position["id"] == 99

    deleted_position = app.routes["DELETE /users/{username}/portfolio/positions/{position_id}"](
        "alice", position_id=99, session_id="valid-session"
    )
    assert deleted_position["deleted"] is True

    rules = app.routes["/users/{username}/alerts/rules"]("alice", session_id="valid-session")
    assert len(rules) == 1

    payload_rule = type(
        "RulePayload",
        (),
        {"ticker": "AAPL", "alert_type": "rsi_gt_70", "threshold": None, "active": True},
    )()
    created_rule = app.routes["POST /users/{username}/alerts/rules"](
        "alice", payload=payload_rule, session_id="valid-session"
    )
    assert created_rule["id"] == 5

    deleted_rule = app.routes["DELETE /users/{username}/alerts/rules/{rule_id}"](
        "alice", rule_id=5, session_id="valid-session"
    )
    assert deleted_rule["deleted"] is True

    payload_watchlist = type("WatchlistPayload", (), {"name": "Tech"})()
    created_watchlist = app.routes["POST /users/{username}/watchlists"](
        "alice", payload=payload_watchlist, session_id="valid-session"
    )
    assert created_watchlist["id"] == 1

    payload_item = type("ItemPayload", (), {"ticker": "NVDA"})()
    added_item = app.routes["POST /users/{username}/watchlists/{watchlist_id}/items"](
        "alice", watchlist_id=1, payload=payload_item, session_id="valid-session"
    )
    assert added_item["added"] is True

    removed_item = app.routes["DELETE /users/{username}/watchlists/{watchlist_id}/items/{ticker}"](
        "alice",
        watchlist_id=1,
        ticker="NVDA",
        session_id="valid-session",
    )
    assert removed_item["deleted"] is True

    metrics = app.routes["/metrics"]()
    assert "counters" in metrics

    prom = app.routes["/metrics/prometheus"]()
    assert isinstance(prom, str)
    assert "quantvision_counter_total" in prom

    usage = app.routes["/analytics/usage/summary"](limit=5)
    assert "funnel" in usage
    assert "top_features" in usage

    exp_payload = type(
        "ExperimentPayload",
        (),
        {
            "name": "cta_experiment",
            "feature": "dashboard",
            "variants": ["control", "treatment"],
            "hypothesis": "Treatment improves click-through",
        },
    )()
    created_experiment = app.routes["POST /analytics/experiments"](payload=exp_payload)
    assert created_experiment["status"] == "created"

    experiments = app.routes["/analytics/experiments"]()
    assert any(item["name"] == "cta_experiment" for item in experiments)

    assignment_payload = type("AssignmentPayload", (), {"username": "alice"})()
    assignment = app.routes["POST /analytics/experiments/{name}/assignment"](
        "cta_experiment", payload=assignment_payload
    )
    assert assignment["variant"] in {"control", "treatment"}

    conversion_payload = type("ConversionPayload", (), {"username": "alice"})()
    conversion = app.routes["POST /analytics/experiments/{name}/conversion"](
        "cta_experiment", payload=conversion_payload
    )
    assert conversion["converted"] is True

    experiment_summary = app.routes["/analytics/experiments/{name}/summary"]("cta_experiment")
    assert isinstance(experiment_summary, list)
    assert len(experiment_summary) >= 1

    detailed = app.routes["/health/detailed"]()
    assert "status" in detailed

    caught = False
    try:
        app.routes["/users/{username}/alerts/history"]("alice", limit=0, session_id="valid-session")
    except FakeHTTPException as exc:
        caught = True
        assert exc.status_code == 400
    assert caught is True


def test_create_app_forbidden_by_rbac(monkeypatch) -> None:
    class FakeApp:
        def __init__(self, title: str, version: str):
            self.routes = {}

        def get(self, path: str):
            def decorator(func):
                self.routes[path] = func
                return func

            return decorator

    class FakeAuth:
        def get_user_role(self, username: str) -> str:
            return "GUEST"

        def can_access_module(self, username: str, module_name: str) -> bool:
            return False

        def validate_session_owner(self, session_id: str, username: str) -> bool:
            return True

    class FakeHTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code

    monkeypatch.setattr(api_main, "FastAPI", FakeApp)
    monkeypatch.setattr(api_main, "HTTPException", FakeHTTPException)

    app = api_main.create_app(FakeAuth())
    denied = False
    try:
        app.routes["/users/{username}/portfolio/summary"]("guest", session_id="valid")
    except FakeHTTPException as exc:
        denied = True
        assert exc.status_code == 403
    assert denied is True
