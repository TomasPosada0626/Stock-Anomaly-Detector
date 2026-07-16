import logging

from services.observability import log_event, metric


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
