import os
from typing import Callable, Optional, Tuple

import pandas as pd
import yfinance as yf

from services.observability import get_logger

DownloadFn = Callable[..., pd.DataFrame]
logger = get_logger("market_data_service")


def ensure_data_dir(data_dir: str) -> None:
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)


def _extract_ticker_columns(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.xs(ticker, axis=1, level=1)
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    return df


def _covers_date_range(df: pd.DataFrame, start_date, end_date) -> bool:
    if df.empty:
        return False
    df_dates = pd.to_datetime(df.index)
    return df_dates.min() <= pd.to_datetime(start_date) and df_dates.max() >= pd.to_datetime(
        end_date
    )


def load_cached_ticker_data(csv_path: str, ticker: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, index_col=0, header=[0, 1], parse_dates=True)
    return _extract_ticker_columns(df, ticker)


def download_ticker_data(
    ticker: str, start_date, end_date, download_fn: DownloadFn = yf.download
) -> pd.DataFrame:
    return download_fn(ticker, start=start_date, end=end_date)


def get_ticker_data(
    ticker: str,
    start_date,
    end_date,
    data_dir: str = "data",
    download_fn: DownloadFn = yf.download,
) -> Tuple[pd.DataFrame, bool, Optional[str]]:
    ensure_data_dir(data_dir)
    csv_path = os.path.join(data_dir, f"{ticker}_10y.csv")

    if os.path.exists(csv_path):
        try:
            cached = load_cached_ticker_data(csv_path, ticker)
            if _covers_date_range(cached, start_date, end_date):
                logger.info("cache_hit ticker=%s path=%s", ticker, csv_path)
                return cached, False, None
        except Exception as cache_error:
            # Corrupt or schema-incompatible cache should not block fresh download.
            logger.warning("cache_read_failed ticker=%s error=%s", ticker, str(cache_error))

    downloaded = download_ticker_data(ticker, start_date, end_date, download_fn=download_fn)
    if downloaded.empty:
        logger.info("download_empty ticker=%s", ticker)
        return downloaded, True, f"No data found for {ticker} in selected date range."

    downloaded.to_csv(csv_path)
    logger.info("download_saved ticker=%s path=%s", ticker, csv_path)
    return downloaded, True, None


def add_return_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    # Keep a single Close column if source data contains duplicated labels.
    if isinstance(result.columns, pd.Index) and (result.columns == "Close").sum() > 1:
        result = result.loc[:, ~result.columns.duplicated(keep="first")]

    close_col = result["Close"]
    if not isinstance(close_col, pd.Series):
        close_col = close_col.squeeze()
        if isinstance(close_col, pd.DataFrame):
            close_col = close_col.iloc[:, 0]
    result["Close"] = pd.to_numeric(close_col, errors="coerce")
    result["Return"] = result["Close"].pct_change()
    return result
