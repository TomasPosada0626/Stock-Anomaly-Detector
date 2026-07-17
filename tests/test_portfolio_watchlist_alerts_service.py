import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from services.alerts_service import AlertRule, AlertsService
from services.portfolio_service import PortfolioService, PositionInput
from services.watchlist_service import WatchlistInput, WatchlistService


def test_portfolio_service_add_and_metrics(tmp_path) -> None:
    db_path = str(tmp_path / "quantvision.db")
    service = PortfolioService(db_path=db_path)

    service.add_position(
        PositionInput(
            username="alice",
            ticker="AAPL",
            quantity=10,
            buy_price=100,
            buy_date="2025-01-01",
        )
    )
    positions = service.list_positions("alice")
    assert len(positions) == 1

    metrics = service.compute_portfolio_metrics("alice", {"AAPL": 120.0})
    assert metrics["Current Value"] == 1200.0
    assert metrics["PnL"] == 200.0

    pos_id = int(positions.iloc[0]["id"])
    service.remove_position(pos_id, "alice")
    assert service.list_positions("alice").empty
    empty_metrics = service.compute_portfolio_metrics("alice", {})
    assert empty_metrics["Invested Capital"] == 0.0


def test_watchlist_service_create_add_remove(tmp_path) -> None:
    db_path = str(tmp_path / "quantvision.db")
    service = WatchlistService(db_path=db_path)

    watchlist_id = service.create_watchlist(WatchlistInput(username="alice", name="Tech"))
    service.add_ticker(watchlist_id, "MSFT")
    items = service.list_items(watchlist_id)
    assert "MSFT" in items["ticker"].tolist()

    service.remove_ticker(watchlist_id, "MSFT")
    items_after = service.list_items(watchlist_id)
    assert items_after.empty

    watchlists = service.list_watchlists("alice")
    assert watchlist_id in watchlists["id"].tolist()
    service.delete_watchlist(watchlist_id, "alice")
    assert service.list_watchlists("alice").empty


def test_alerts_service_rules_and_history(tmp_path) -> None:
    db_path = str(tmp_path / "quantvision.db")
    service = AlertsService(db_path=db_path)

    rule_id = service.create_rule(
        AlertRule(username="alice", ticker="AAPL", alert_type="rsi_gt_70", threshold=None)
    )
    rules = service.list_rules("alice")
    assert rule_id in rules["id"].tolist()

    service.emit_alert("alice", "AAPL", "rsi_gt_70", "RSI reached 75")
    history = service.list_history("alice")
    assert not history.empty
    assert history.iloc[0]["ticker"] == "AAPL"

    service.delete_rule(rule_id, "alice")
    assert service.list_rules("alice").empty
