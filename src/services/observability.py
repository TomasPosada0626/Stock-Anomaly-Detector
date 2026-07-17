import logging
import os
import time
from typing import Any

from config import APP_LOG_DIR

_METRICS_COUNTERS: dict[str, int] = {}
_METRICS_TIMINGS: dict[str, list[float]] = {}


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

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
    payload = " ".join(f"{k}={fields[k]}" for k in sorted(fields))
    logger.info("event=%s %s", event, payload)


def metric(logger: logging.Logger, name: str, value: int = 1, **tags: Any) -> None:
    payload = " ".join(f"{k}={tags[k]}" for k in sorted(tags))
    logger.info("metric=%s value=%s %s", name, value, payload)
    _METRICS_COUNTERS[name] = _METRICS_COUNTERS.get(name, 0) + int(value)


def record_timing(logger: logging.Logger, name: str, duration_seconds: float, **tags: Any) -> None:
    payload = " ".join(f"{k}={tags[k]}" for k in sorted(tags))
    logger.info("timing=%s duration_seconds=%.6f %s", name, duration_seconds, payload)
    _METRICS_TIMINGS.setdefault(name, []).append(float(duration_seconds))


def timed(metric_name: str, logger: logging.Logger):
    start = time.perf_counter()

    class _TimingContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            elapsed = time.perf_counter() - start
            record_timing(logger, metric_name, elapsed)
            return False

    return _TimingContext()


def get_metrics_snapshot() -> dict[str, Any]:
    averages = {
        key: (sum(values) / len(values) if values else 0.0)
        for key, values in _METRICS_TIMINGS.items()
    }
    return {
        "counters": dict(_METRICS_COUNTERS),
        "timing_count": {key: len(values) for key, values in _METRICS_TIMINGS.items()},
        "timing_avg_seconds": averages,
    }


def reset_metrics() -> None:
    _METRICS_COUNTERS.clear()
    _METRICS_TIMINGS.clear()
