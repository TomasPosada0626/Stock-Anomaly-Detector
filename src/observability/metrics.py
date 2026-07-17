from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

anomalies_detected_total = Counter(
    "quantvision_anomalies_detected_total",
    "Total anomalies detected",
    ["method", "ticker"],
)

logins_total = Counter(
    "quantvision_logins_total",
    "Total login attempts",
    ["success"],
)

anomaly_detection_duration = Histogram(
    "quantvision_anomaly_detection_duration_seconds",
    "Time to detect anomalies",
    ["method"],
)

active_sessions = Gauge(
    "quantvision_active_sessions",
    "Number of active sessions",
)

trades_executed_total = Counter(
    "quantvision_trades_executed_total",
    "Total simulated trades executed",
)

scheduler_failures_total = Counter(
    "quantvision_scheduler_failures_total",
    "Total scheduler failures",
)


def record_anomalies_detected(method: str, count: int, ticker: str = "unknown") -> None:
    anomalies_detected_total.labels(method=method, ticker=ticker).inc(max(0, int(count)))


def record_method_runtime(method: str, duration_seconds: float) -> None:
    anomaly_detection_duration.labels(method=method).observe(max(0.0, float(duration_seconds)))


def record_trades_executed(trade_count: int) -> None:
    trades_executed_total.inc(max(0, int(trade_count)))


def record_scheduler_failure(failure_count: int) -> None:
    scheduler_failures_total.inc(max(0, int(failure_count)))


def record_login_attempt(success: bool) -> None:
    logins_total.labels(success=str(bool(success)).lower()).inc()


def set_active_sessions(count: int) -> None:
    active_sessions.set(max(0, int(count)))
