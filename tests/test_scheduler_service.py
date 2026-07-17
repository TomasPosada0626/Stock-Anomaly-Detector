import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from services.alerts_service import AlertRule, AlertsService
import services.scheduler_service as scheduler_module
from services.scheduler_service import AlertScheduler


def test_scheduler_evaluates_rules_once(tmp_path) -> None:
    db_path = str(tmp_path / "quantvision.db")
    alerts = AlertsService(db_path=db_path)
    alerts.create_rule(AlertRule(username="alice", ticker="AAPL", alert_type="rsi_gt_70"))

    idx = pd.date_range("2025-01-01", periods=5, freq="D")
    market_df = pd.DataFrame(
        {
            "Close": [100, 102, 103, 104, 106],
            "RSI_14": [50, 60, 68, 71, 75],
        },
        index=idx,
    )

    scheduler = AlertScheduler(alerts, fetch_market_data=lambda _: market_df)
    triggered = scheduler.evaluate_alerts_once("alice")

    assert triggered >= 1
    history = alerts.list_history("alice")
    assert not history.empty


def test_scheduler_handles_empty_rules(tmp_path) -> None:
    db_path = str(tmp_path / "quantvision.db")
    alerts = AlertsService(db_path=db_path)
    scheduler = AlertScheduler(alerts, fetch_market_data=lambda _: pd.DataFrame())
    assert scheduler.evaluate_alerts_once("nobody") == 0


def test_scheduler_multiple_rule_types_and_start_stop(monkeypatch, tmp_path) -> None:
    class FakeBackgroundScheduler:
        def __init__(self):
            self.running = False
            self.jobs = []

        def add_job(self, *args, **kwargs):
            self.jobs.append((args, kwargs))

        def start(self):
            self.running = True

        def shutdown(self, wait: bool = False):
            self.running = False

    monkeypatch.setattr(scheduler_module, "BackgroundScheduler", FakeBackgroundScheduler)

    db_path = str(tmp_path / "quantvision.db")
    alerts = AlertsService(db_path=db_path)
    alerts.create_rule(AlertRule(username="bob", ticker="AAPL", alert_type="price_change_pct", threshold=1.0))
    alerts.create_rule(AlertRule(username="bob", ticker="AAPL", alert_type="new_high"))
    alerts.create_rule(AlertRule(username="bob", ticker="AAPL", alert_type="new_low"))

    idx = pd.date_range("2025-01-01", periods=5, freq="D")
    market_df = pd.DataFrame(
        {
            "Close": [100, 101, 102, 103, 106],
            "RSI_14": [50, 50, 50, 50, 50],
        },
        index=idx,
    )
    scheduler = AlertScheduler(alerts, fetch_market_data=lambda _: market_df)

    triggered = scheduler.evaluate_alerts_once("bob")
    assert triggered >= 2

    assert scheduler.start("bob", interval_minutes=5) is True
    assert scheduler.scheduler is not None
    assert scheduler.scheduler.running is True
    scheduler.stop()
    assert scheduler.scheduler.running is False
