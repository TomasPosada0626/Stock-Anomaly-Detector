from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from config import (
    SCHEDULER_HEARTBEAT_FILE,
    SCHEDULER_INTERVAL_MINUTES,
    SCHEDULER_MAX_CONSECUTIVE_FAILURES,
    SCHEDULER_MAX_CYCLES,
    SCHEDULER_RUN_CONTINUOUS,
    SCHEDULER_WORKER_MODE,
)
from services.alerts_service import AlertsService
from services.indicators_service import add_indicators
from services.market_data_service import add_return_features, get_ticker_data
from services.scheduler_service import AlertScheduler


def _fetch_market_frame(ticker: str):
    end = datetime.today().strftime("%Y-%m-%d")
    df, _, _ = get_ticker_data(ticker=ticker, start_date="2019-01-01", end_date=end)
    if df.empty:
        return df
    return add_indicators(add_return_features(df))


def _write_heartbeat(cycle: int, summary: dict[str, int], error: str = "") -> None:
    heartbeat_path = Path(SCHEDULER_HEARTBEAT_FILE)
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now().isoformat(),
        "cycle": int(cycle),
        "summary": summary,
        "error": error,
    }
    heartbeat_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    alerts = AlertsService()
    scheduler = AlertScheduler(alerts, fetch_market_data=_fetch_market_frame)

    if SCHEDULER_WORKER_MODE:
        print(
            "QuantVision scheduler worker mode enabled "
            f"(interval={SCHEDULER_INTERVAL_MINUTES}m max_cycles={SCHEDULER_MAX_CYCLES or 'infinite'})"
        )
        scheduler.run_continuous(
            interval_minutes=SCHEDULER_INTERVAL_MINUTES,
            max_cycles=SCHEDULER_MAX_CYCLES,
            max_consecutive_failures=SCHEDULER_MAX_CONSECUTIVE_FAILURES,
            cycle_hook=lambda cycle, summary: _write_heartbeat(cycle, summary, error=""),
            error_hook=lambda cycle, message: _write_heartbeat(cycle, {}, error=message),
        )
        return

    started = scheduler.start(username="system", interval_minutes=SCHEDULER_INTERVAL_MINUTES)
    if started:
        print(
            f"QuantVision scheduler running every {SCHEDULER_INTERVAL_MINUTES} minute(s) with APScheduler"
        )
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            scheduler.stop()
            print("Scheduler stopped")
        return

    if SCHEDULER_RUN_CONTINUOUS:
        print(
            f"APScheduler unavailable. Falling back to continuous loop every {SCHEDULER_INTERVAL_MINUTES} minute(s)."
        )
        scheduler.run_continuous(
            interval_minutes=SCHEDULER_INTERVAL_MINUTES,
            max_cycles=SCHEDULER_MAX_CYCLES,
            max_consecutive_failures=SCHEDULER_MAX_CONSECUTIVE_FAILURES,
            cycle_hook=lambda cycle, summary: _write_heartbeat(cycle, summary, error=""),
            error_hook=lambda cycle, message: _write_heartbeat(cycle, {}, error=message),
        )
        return

    summary = scheduler.evaluate_all_users_once()
    print(f"Scheduler single pass summary: {summary}")


if __name__ == "__main__":
    main()
