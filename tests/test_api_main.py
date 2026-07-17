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

    role = app.routes["/users/{username}/role"]("alice")
    assert role["role"] == "ANALYST"

    summary = app.routes["/users/{username}/portfolio/summary"]("alice", prices="AAPL:100")
    assert summary["PnL"] == 10.0

    history = app.routes["/users/{username}/alerts/history"]("alice", limit=10)
    assert len(history) == 1

    watchlists = app.routes["/users/{username}/watchlists"]("alice")
    assert len(watchlists) == 1

    items = app.routes["/users/{username}/watchlists/{watchlist_id}/items"]("alice", watchlist_id=1)
    assert len(items) == 2

    indicators = app.routes["/analytics/{ticker}/indicators"]("aapl")
    assert indicators["ticker"] == "AAPL"

    anomalies = app.routes["/analytics/{ticker}/anomalies"]("aapl")
    assert "zscore_count" in anomalies

    backtest = app.routes["/analytics/{ticker}/backtest"]("aapl")
    assert "Return %" in backtest

    report = app.routes["/users/{username}/reports/portfolio"]("alice", prices="AAPL:100")
    assert report["pdf_bytes"] == 3

    positions = app.routes["/users/{username}/portfolio/positions"]("alice")
    assert len(positions) == 1

    payload_position = type(
        "PositionPayload",
        (),
        {"ticker": "AAPL", "quantity": 1.0, "buy_price": 100.0, "buy_date": "2026-01-01"},
    )()
    created_position = app.routes["POST /users/{username}/portfolio/positions"](
        "alice", payload=payload_position
    )
    assert created_position["id"] == 99

    deleted_position = app.routes["DELETE /users/{username}/portfolio/positions/{position_id}"](
        "alice", position_id=99
    )
    assert deleted_position["deleted"] is True

    rules = app.routes["/users/{username}/alerts/rules"]("alice")
    assert len(rules) == 1

    payload_rule = type(
        "RulePayload",
        (),
        {"ticker": "AAPL", "alert_type": "rsi_gt_70", "threshold": None, "active": True},
    )()
    created_rule = app.routes["POST /users/{username}/alerts/rules"]("alice", payload=payload_rule)
    assert created_rule["id"] == 5

    deleted_rule = app.routes["DELETE /users/{username}/alerts/rules/{rule_id}"]("alice", rule_id=5)
    assert deleted_rule["deleted"] is True

    payload_watchlist = type("WatchlistPayload", (), {"name": "Tech"})()
    created_watchlist = app.routes["POST /users/{username}/watchlists"](
        "alice", payload=payload_watchlist
    )
    assert created_watchlist["id"] == 1

    payload_item = type("ItemPayload", (), {"ticker": "NVDA"})()
    added_item = app.routes["POST /users/{username}/watchlists/{watchlist_id}/items"](
        "alice", watchlist_id=1, payload=payload_item
    )
    assert added_item["added"] is True

    removed_item = app.routes["DELETE /users/{username}/watchlists/{watchlist_id}/items/{ticker}"](
        "alice",
        watchlist_id=1,
        ticker="NVDA",
    )
    assert removed_item["deleted"] is True

    metrics = app.routes["/metrics"]()
    assert "counters" in metrics

    detailed = app.routes["/health/detailed"]()
    assert "status" in detailed

    caught = False
    try:
        app.routes["/users/{username}/alerts/history"]("alice", limit=0)
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

    class FakeHTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code

    monkeypatch.setattr(api_main, "FastAPI", FakeApp)
    monkeypatch.setattr(api_main, "HTTPException", FakeHTTPException)

    app = api_main.create_app(FakeAuth())
    denied = False
    try:
        app.routes["/users/{username}/portfolio/summary"]("guest")
    except FakeHTTPException as exc:
        denied = True
        assert exc.status_code == 403
    assert denied is True
