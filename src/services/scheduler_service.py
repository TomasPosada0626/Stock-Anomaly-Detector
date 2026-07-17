from __future__ import annotations

import time
from typing import Callable

import pandas as pd

from services.alerts_service import AlertsService
from services.observability import get_logger

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:  # pragma: no cover - optional dependency
    BackgroundScheduler = None  # type: ignore[assignment]


class AlertScheduler:
    def __init__(
        self, alerts_service: AlertsService, fetch_market_data: Callable[[str], pd.DataFrame]
    ) -> None:
        self.alerts_service = alerts_service
        self.fetch_market_data = fetch_market_data
        self.logger = get_logger("scheduler_service")
        self.scheduler = BackgroundScheduler() if BackgroundScheduler else None

    def evaluate_alerts_once(self, username: str) -> int:
        rules = self.alerts_service.list_rules(username)
        if rules.empty:
            return 0

        triggered_count = 0
        for _, row in rules[rules["active"] == 1].iterrows():
            ticker = str(row["ticker"]).upper()
            frame = self.fetch_market_data(ticker)
            if frame.empty or len(frame) < 3:
                continue

            current = frame.iloc[-1]
            previous = frame.iloc[-2]
            alert_type = str(row["alert_type"])
            threshold = row.get("threshold")
            message = ""
            triggered = False

            if alert_type == "rsi_gt_70":
                triggered = float(current.get("RSI_14", 0)) > 70
                message = f"RSI reached {current.get('RSI_14', 0):.2f}"
            elif alert_type == "rsi_lt_30":
                triggered = float(current.get("RSI_14", 100)) < 30
                message = f"RSI dropped to {current.get('RSI_14', 0):.2f}"
            elif alert_type == "price_change_pct":
                target = float(threshold if threshold is not None else 5)
                variation = ((float(current["Close"]) / float(previous["Close"])) - 1) * 100
                triggered = abs(variation) >= target
                message = f"Price variation {variation:.2f}%"
            elif alert_type == "new_high":
                triggered = float(current["Close"]) >= float(frame["Close"].tail(252).max())
                message = "New 52-week high"
            elif alert_type == "new_low":
                triggered = float(current["Close"]) <= float(frame["Close"].tail(252).min())
                message = "New 52-week low"

            if triggered:
                self.alerts_service.emit_alert(username, ticker, alert_type, message)
                triggered_count += 1
        self.logger.info(
            "scheduled_alert_evaluation username=%s triggered=%s", username, triggered_count
        )
        return triggered_count

    def start(self, username: str, interval_minutes: int = 15) -> bool:
        if not self.scheduler:
            self.logger.warning("apscheduler_unavailable")
            return False
        self.scheduler.add_job(
            self.evaluate_alerts_once,
            "interval",
            minutes=max(1, int(interval_minutes)),
            kwargs={"username": username},
            id=f"alerts_{username}",
            replace_existing=True,
        )
        self.scheduler.start()
        return True

    def evaluate_all_users_once(self) -> dict[str, int]:
        owners = self.alerts_service.list_rule_owners()
        summary: dict[str, int] = {}
        for username in owners:
            summary[username] = self.evaluate_alerts_once(username)
        self.logger.info("scheduled_alert_evaluation_all summary=%s", summary)
        return summary

    def run_continuous(self, interval_minutes: int = 15) -> None:
        wait_seconds = max(1, int(interval_minutes)) * 60
        self.logger.info("scheduler_continuous_started interval_seconds=%s", wait_seconds)
        try:
            while True:
                self.evaluate_all_users_once()
                time.sleep(wait_seconds)
        except KeyboardInterrupt:
            self.logger.info("scheduler_continuous_stopped")

    def stop(self) -> None:
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
