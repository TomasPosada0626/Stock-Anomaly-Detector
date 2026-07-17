from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Any, Callable

import pandas as pd

_executor = ThreadPoolExecutor(max_workers=2)
_jobs: dict[str, Future] = {}
_jobs_lock = Lock()


def paginate_dataframe(
    df: pd.DataFrame,
    limit: int = 50,
    sort_by: str | None = None,
    descending: bool = True,
) -> pd.DataFrame:
    if df.empty:
        return df

    output = df.copy()
    if sort_by and sort_by in output.columns:
        output = output.sort_values(by=sort_by, ascending=not descending)
    return output.head(max(1, int(limit)))


def submit_async_job(job_id: str, fn: Callable[..., Any], *args, **kwargs) -> None:
    with _jobs_lock:
        _jobs[job_id] = _executor.submit(fn, *args, **kwargs)


def get_async_job_result(job_id: str) -> tuple[str, Any]:
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
