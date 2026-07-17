from integrations.webhooks import WebhookNotifier, WebhookPayload


def test_webhook_notifier_dispatches_payload() -> None:
    captured = {}

    def fake_sender(url: str, payload_bytes: bytes) -> int:
        captured["url"] = url
        captured["body"] = payload_bytes.decode("utf-8")
        return 202

    notifier = WebhookNotifier(sender=fake_sender)
    result = notifier.send(
        "https://example.com/hook",
        WebhookPayload(event="alert_triggered", message="AAPL anomaly detected"),
    )

    assert result["success"] is True
    assert result["status"] == 202
    assert captured["url"] == "https://example.com/hook"
    assert "alert_triggered" in captured["body"]


def test_webhook_notifier_rejects_invalid_url() -> None:
    notifier = WebhookNotifier(sender=lambda u, p: 200)

    error = None
    try:
        notifier.send("ftp://invalid", WebhookPayload(event="x", message="y"))
    except ValueError as exc:
        error = str(exc)

    assert error is not None
    assert "http:// or https://" in error
