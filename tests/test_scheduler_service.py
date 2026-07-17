import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import services.scheduler_service as scheduler_module
from services.alerts_service import AlertRule, AlertsService
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
    alerts.create_rule(
        AlertRule(username="bob", ticker="AAPL", alert_type="price_change_pct", threshold=1.0)
    )
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


def test_scheduler_start_returns_false_when_dependency_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(scheduler_module, "BackgroundScheduler", None)
    alerts = AlertsService(db_path=str(tmp_path / "qv.db"))
    scheduler = AlertScheduler(alerts, fetch_market_data=lambda _: pd.DataFrame())
    assert scheduler.start("alice", interval_minutes=5) is False


def test_scheduler_evaluate_all_users_once(tmp_path) -> None:
    db_path = str(tmp_path / "quantvision.db")
    alerts = AlertsService(db_path=db_path)
    alerts.create_rule(AlertRule(username="alice", ticker="AAPL", alert_type="new_high"))
    alerts.create_rule(AlertRule(username="bob", ticker="AAPL", alert_type="new_high"))

    idx = pd.date_range("2025-01-01", periods=5, freq="D")
    market_df = pd.DataFrame({"Close": [100, 101, 102, 103, 104]}, index=idx)

    scheduler = AlertScheduler(alerts, fetch_market_data=lambda _: market_df)
    summary = scheduler.evaluate_all_users_once()
    assert "alice" in summary
    assert "bob" in summary


def test_scheduler_run_continuous_stops_on_keyboard_interrupt(monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "quantvision.db")
    alerts = AlertsService(db_path=db_path)
    scheduler = AlertScheduler(alerts, fetch_market_data=lambda _: pd.DataFrame())

    monkeypatch.setattr(scheduler, "evaluate_all_users_once", lambda: {"system": 0})

    call_count = {"n": 0}

    def fake_sleep(seconds: int):
        call_count["n"] += 1
        raise KeyboardInterrupt()

    monkeypatch.setattr(scheduler_module.time, "sleep", fake_sleep)
    scheduler.run_continuous(interval_minutes=1)
    assert call_count["n"] == 1


def test_scheduler_run_continuous_respects_max_cycles(monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "quantvision.db")
    alerts = AlertsService(db_path=db_path)
    scheduler = AlertScheduler(alerts, fetch_market_data=lambda _: pd.DataFrame())

    cycles = []
    monkeypatch.setattr(scheduler, "evaluate_all_users_once", lambda: {"alice": 1})
    monkeypatch.setattr(scheduler_module.time, "sleep", lambda seconds: None)

    scheduler.run_continuous(
        interval_minutes=1,
        max_cycles=2,
        cycle_hook=lambda cycle, summary: cycles.append((cycle, summary)),
    )

    assert len(cycles) == 2
    assert cycles[0][0] == 1
    assert cycles[1][0] == 2


def test_scheduler_run_continuous_stops_after_max_failures(monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "quantvision.db")
    alerts = AlertsService(db_path=db_path)
    scheduler = AlertScheduler(alerts, fetch_market_data=lambda _: pd.DataFrame())

    failures = []

    def _raise_cycle_error():
        raise RuntimeError("cycle failed")

    monkeypatch.setattr(scheduler, "evaluate_all_users_once", _raise_cycle_error)
    monkeypatch.setattr(scheduler_module.time, "sleep", lambda seconds: None)

    scheduler.run_continuous(
        interval_minutes=1,
        max_consecutive_failures=2,
        error_hook=lambda cycle, message: failures.append((cycle, message)),
    )

    assert len(failures) == 2
    assert failures[0][0] == 1
    assert "cycle failed" in failures[0][1]
