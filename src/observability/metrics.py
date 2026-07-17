from __future__ import annotations

from services.observability import get_logger, metric, record_timing

_logger = get_logger("observability_metrics")


def record_anomalies_detected(method: str, count: int) -> None:
    metric(_logger, "anomalies_detected_total", value=max(0, int(count)), method=method)


def record_method_runtime(method: str, duration_seconds: float) -> None:
    record_timing(_logger, "anomaly_method_runtime_seconds", duration_seconds, method=method)


def record_trades_executed(trade_count: int) -> None:
    metric(_logger, "trades_executed_total", value=max(0, int(trade_count)))


def record_scheduler_failure(failure_count: int) -> None:
    metric(_logger, "scheduler_failures_total", value=max(0, int(failure_count)))
