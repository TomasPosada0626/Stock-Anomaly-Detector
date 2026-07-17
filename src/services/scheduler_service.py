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

    def run_continuous(
        self,
        interval_minutes: int = 15,
        max_cycles: int = 0,
        max_consecutive_failures: int = 10,
        cycle_hook: Callable[[int, dict[str, int]], None] | None = None,
        error_hook: Callable[[int, str], None] | None = None,
    ) -> None:
        wait_seconds = max(1, int(interval_minutes)) * 60
        self.logger.info(
            "scheduler_continuous_started interval_seconds=%s max_cycles=%s max_consecutive_failures=%s",
            wait_seconds,
            max_cycles,
            max_consecutive_failures,
        )
        cycles_run = 0
        consecutive_failures = 0
        try:
            while True:
                if max_cycles > 0 and cycles_run >= max_cycles:
                    self.logger.info(
                        "scheduler_continuous_max_cycles_reached cycles=%s", cycles_run
                    )
                    return

                cycle_number = cycles_run + 1
                try:
                    summary = self.evaluate_all_users_once()
                    consecutive_failures = 0
                    if cycle_hook is not None:
                        cycle_hook(cycle_number, summary)
                except Exception as exc:  # pragma: no cover - resiliency path
                    consecutive_failures += 1
                    error_message = str(exc)
                    self.logger.exception(
                        "scheduler_continuous_cycle_failed cycle=%s consecutive_failures=%s error=%s",
                        cycle_number,
                        consecutive_failures,
                        error_message,
                    )
                    if error_hook is not None:
                        error_hook(cycle_number, error_message)
                    if consecutive_failures >= max_consecutive_failures:
                        self.logger.error(
                            "scheduler_continuous_stopping_after_failures failures=%s",
                            consecutive_failures,
                        )
                        return

                cycles_run += 1
                time.sleep(wait_seconds)
        except KeyboardInterrupt:
            self.logger.info("scheduler_continuous_stopped")

    def stop(self) -> None:
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
