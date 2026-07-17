from __future__ import annotations

from datetime import datetime

from config import SCHEDULER_INTERVAL_MINUTES
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


def main() -> None:
    alerts = AlertsService()
    scheduler = AlertScheduler(alerts, fetch_market_data=_fetch_market_frame)
    started = scheduler.start(username="system", interval_minutes=SCHEDULER_INTERVAL_MINUTES)
    if started:
        print(f"QuantVision scheduler running every {SCHEDULER_INTERVAL_MINUTES} minute(s)")
    else:
        # Fallback for environments where APScheduler is unavailable.
        triggered = scheduler.evaluate_alerts_once("system")
        print(f"Scheduler dependency unavailable. Single pass executed: {triggered} alerts triggered")


if __name__ == "__main__":
    main()
