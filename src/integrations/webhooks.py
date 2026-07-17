from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable
from urllib import request


@dataclass(frozen=True)
class WebhookPayload:
    event: str
    message: str
    source: str = "quantvision"


class WebhookNotifier:
    def __init__(self, sender: Callable[[str, bytes], int] | None = None) -> None:
        self._sender = sender or self._default_sender

    @staticmethod
    def _default_sender(url: str, payload_bytes: bytes) -> int:
        req = request.Request(
            url=url,
            data=payload_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=10) as response:  # nosec B310
            return int(getattr(response, "status", 200))

    def send(self, url: str, payload: WebhookPayload) -> dict[str, object]:
        endpoint = url.strip()
        if not endpoint.lower().startswith(("http://", "https://")):
            raise ValueError("webhook url must start with http:// or https://")

        body = {
            "event": payload.event,
            "message": payload.message,
            "source": payload.source,
        }
        raw = json.dumps(body).encode("utf-8")
        status = int(self._sender(endpoint, raw))
        return {
            "url": endpoint,
            "status": status,
            "success": 200 <= status < 300,
            "payload": body,
        }
