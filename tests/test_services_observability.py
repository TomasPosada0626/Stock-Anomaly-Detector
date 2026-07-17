import json
import logging

from services.observability import (
    JsonLogFormatter,
    get_metrics_snapshot,
    get_prometheus_metrics_text,
    metric,
    record_timing,
    reset_metrics,
)


def test_json_log_formatter_includes_core_fields() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="quantvision.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    payload = json.loads(formatter.format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "quantvision.test"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload


def test_metric_and_timing_are_exposed_in_prometheus_snapshot() -> None:
    logger = logging.getLogger("test_services_observability")
    reset_metrics()

    metric(logger, "auth_login_success", value=2, role="ANALYST")
    record_timing(logger, "anomaly_run", 0.125)

    snapshot = get_metrics_snapshot()
    assert snapshot["counters"]["auth_login_success"] == 2
    assert snapshot["timing_count"]["anomaly_run"] == 1

    output = get_prometheus_metrics_text(namespace="quantvision")
    assert 'quantvision_counter_total{metric="auth_login_success"} 2' in output
    assert 'quantvision_timing_avg_seconds{metric="anomaly_run"}' in output
