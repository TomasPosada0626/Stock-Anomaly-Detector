import logging

from services.observability import (
    get_metrics_snapshot,
    log_event,
    metric,
    record_timing,
    reset_metrics,
    timed,
)


def test_log_event_emits_structured_payload(caplog) -> None:
    logger = logging.getLogger("test_observability_event")
    with caplog.at_level(logging.INFO):
        log_event(logger, "auth.login", user="alice", status="ok")

    assert any("event=auth.login" in message for message in caplog.messages)
    assert any("status=ok" in message for message in caplog.messages)


def test_metric_emits_structured_payload(caplog) -> None:
    logger = logging.getLogger("test_observability_metric")
    with caplog.at_level(logging.INFO):
        metric(logger, "auth_failed_login", value=2, identifier="alice")

    assert any("metric=auth_failed_login" in message for message in caplog.messages)
    assert any("value=2" in message for message in caplog.messages)


def test_observability_snapshot_and_timing() -> None:
    logger = logging.getLogger("test_observability_timing")
    reset_metrics()

    metric(logger, "x_counter", value=3)
    record_timing(logger, "x_timing", 0.02)
    with timed("ctx_timing", logger):
        _ = 1 + 1

    snapshot = get_metrics_snapshot()
    assert snapshot["counters"]["x_counter"] == 3
    assert snapshot["timing_count"]["x_timing"] == 1
    assert snapshot["timing_count"]["ctx_timing"] >= 1
