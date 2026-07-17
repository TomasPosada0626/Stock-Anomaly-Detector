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

    class FakeAuth:
        def get_user_role(self, username: str) -> str:
            return "ANALYST"

    class FakePortfolio:
        def compute_portfolio_metrics(self, username: str, latest_prices):
            return {"Invested Capital": 100.0, "Current Value": 110.0, "PnL": 10.0, "ROI %": 10.0}

    class FakeAlerts:
        def list_history(self, username: str, limit: int = 100):
            return pd.DataFrame([{"ticker": "AAPL", "alert_type": "rsi_gt_70", "message": "x"}])

    class FakeHTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    monkeypatch.setattr(api_main, "FastAPI", FakeApp)
    monkeypatch.setattr(api_main, "HTTPException", FakeHTTPException)

    app = api_main.create_app(FakeAuth(), FakePortfolio(), FakeAlerts())
    assert app.title == "QuantVision API"

    health = app.routes["/health"]()
    assert health["status"] == "ok"

    role = app.routes["/users/{username}/role"]("alice")
    assert role["role"] == "ANALYST"

    summary = app.routes["/users/{username}/portfolio/summary"]("alice", prices="AAPL:100")
    assert summary["PnL"] == 10.0

    history = app.routes["/users/{username}/alerts/history"]("alice", limit=10)
    assert len(history) == 1

    try:
        app.routes["/users/{username}/alerts/history"]("alice", limit=0)
        assert False
    except FakeHTTPException as exc:
        assert exc.status_code == 400
