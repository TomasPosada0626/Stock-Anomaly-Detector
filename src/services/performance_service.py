from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Any, Callable

import pandas as pd

_executor = ThreadPoolExecutor(max_workers=2)
_jobs: dict[str, Future[Any]] = {}
_jobs_lock = Lock()


def paginate_dataframe(
    df: pd.DataFrame,
    limit: int = 50,
    sort_by: str | None = None,
    descending: bool = True,
) -> pd.DataFrame:
    """Return a sorted, size-limited dataframe view for UI rendering."""
    if df.empty:
        return df

    output = df.copy()
    if sort_by and sort_by in output.columns:
        output = output.sort_values(by=sort_by, ascending=not descending)
    return output.head(max(1, int(limit)))


def submit_async_job(job_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Submit a background task keyed by a caller-provided job id."""
    with _jobs_lock:
        _jobs[job_id] = _executor.submit(fn, *args, **kwargs)


def get_async_job_result(job_id: str) -> tuple[str, Any]:
    """Return status and payload for an asynchronous background job."""
    with _jobs_lock:
        future = _jobs.get(job_id)

    if future is None:
        return "not_found", None
    if not future.done():
        return "running", None

    try:
        result = future.result()
        return "completed", result
    except Exception as exc:  # pragma: no cover - defensive path
        return "failed", str(exc)
