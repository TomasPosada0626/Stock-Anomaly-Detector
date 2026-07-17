from __future__ import annotations

import re
from io import StringIO

import pandas as pd

_VALID_TICKER = re.compile(r"^[A-Z][A-Z0-9._-]{0,9}$")


def sanitize_ticker(value: str) -> str:
    ticker = (value or "").strip().upper()
    if not _VALID_TICKER.match(ticker):
        raise ValueError("invalid ticker format")
    return ticker


def sanitize_csv_upload(content: str, max_rows: int = 200_000) -> pd.DataFrame:
    if not content.strip():
        raise ValueError("empty csv content")

    df = pd.read_csv(StringIO(content))
    if df.empty:
        raise ValueError("csv contains no rows")
    if len(df) > max_rows:
        raise ValueError("csv row limit exceeded")

    suspicious_columns = {"__proto__", "constructor", "eval", "script"}
    columns = {str(col).strip().lower() for col in df.columns}
    if columns.intersection(suspicious_columns):
        raise ValueError("csv contains suspicious column names")
    return df


def require_ticker_whitelist(ticker: str, allowed: set[str]) -> str:
    normalized = sanitize_ticker(ticker)
    if allowed and normalized not in {item.upper() for item in allowed}:
        raise ValueError("ticker not allowed")
    return normalized
