import json
import logging
import os
import time
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, Literal

from config import APP_LOG_DIR

_METRICS_COUNTERS: dict[str, int] = {}
_METRICS_TIMINGS: dict[str, list[float]] = {}


class JsonLogFormatter(logging.Formatter):
    """Render logs as structured JSON records."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def get_logger(name: str) -> logging.Logger:
    """Create or reuse a logger configured for JSON output.

    Args:
        name: Logger name.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = JsonLogFormatter()

    logs_dir = APP_LOG_DIR
    os.makedirs(logs_dir, exist_ok=True)

    file_handler = logging.FileHandler(os.path.join(logs_dir, "app.log"), encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit a structured event log with flattened key/value fields."""
    payload = " ".join(f"{k}={fields[k]}" for k in sorted(fields))
    logger.info("event=%s %s", event, payload)


def metric(logger: logging.Logger, name: str, value: int = 1, **tags: Any) -> None:
    """Track a counter metric and mirror it to logs."""
    payload = " ".join(f"{k}={tags[k]}" for k in sorted(tags))
    logger.info("metric=%s value=%s %s", name, value, payload)
    _METRICS_COUNTERS[name] = _METRICS_COUNTERS.get(name, 0) + int(value)


def record_timing(logger: logging.Logger, name: str, duration_seconds: float, **tags: Any) -> None:
    """Track a timing metric and mirror it to logs."""
    payload = " ".join(f"{k}={tags[k]}" for k in sorted(tags))
    logger.info("timing=%s duration_seconds=%.6f %s", name, duration_seconds, payload)
    _METRICS_TIMINGS.setdefault(name, []).append(float(duration_seconds))


def timed(metric_name: str, logger: logging.Logger) -> AbstractContextManager[object]:
    """Return a context manager that records elapsed time for a code block."""
    start = time.perf_counter()

    class _TimingContext:
        def __enter__(self) -> "_TimingContext":
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> Literal[False]:
            elapsed = time.perf_counter() - start
            record_timing(logger, metric_name, elapsed)
            return False

    return _TimingContext()


def get_metrics_snapshot() -> dict[str, Any]:
    """Return in-memory metric counters and timing aggregates."""
    averages = {
        key: (sum(values) / len(values) if values else 0.0)
        for key, values in _METRICS_TIMINGS.items()
    }
    return {
        "counters": dict(_METRICS_COUNTERS),
        "timing_count": {key: len(values) for key, values in _METRICS_TIMINGS.items()},
        "timing_avg_seconds": averages,
    }


def get_prometheus_metrics_text(namespace: str = "quantvision") -> str:
    """Render in-memory metrics in Prometheus text exposition format."""
    counters = dict(_METRICS_COUNTERS)
    timings = dict(_METRICS_TIMINGS)
    lines = [
        f"# HELP {namespace}_counter_total Aggregated counter metrics",
        f"# TYPE {namespace}_counter_total counter",
    ]
    for metric_name, value in sorted(counters.items()):
        safe_name = metric_name.lower().replace(" ", "_")
        lines.append(f'{namespace}_counter_total{{metric="{safe_name}"}} {int(value)}')

    lines.extend(
        [
            f"# HELP {namespace}_timing_avg_seconds Average timing in seconds",
            f"# TYPE {namespace}_timing_avg_seconds gauge",
        ]
    )
    for metric_name, values in sorted(timings.items()):
        safe_name = metric_name.lower().replace(" ", "_")
        avg = (sum(values) / len(values)) if values else 0.0
        lines.append(f'{namespace}_timing_avg_seconds{{metric="{safe_name}"}} {avg:.8f}')

    return "\n".join(lines) + "\n"


def reset_metrics() -> None:
    """Clear all in-memory metrics (used by tests)."""
    _METRICS_COUNTERS.clear()
    _METRICS_TIMINGS.clear()
