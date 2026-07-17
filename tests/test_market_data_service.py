import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from services import market_data_service
from services.market_data_service import add_return_features, get_ticker_data


def test_get_ticker_data_uses_cache_when_range_covered(tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_path = data_dir / "AAPL_10y.csv"

    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            ("Close", "AAPL"): [10, 11, 12, 13, 14],
            ("Open", "AAPL"): [9, 10, 11, 12, 13],
        },
        index=idx,
    )
    df.to_csv(csv_path)

    downloaded_df, downloaded, warning = get_ticker_data(
        ticker="AAPL",
        start_date=idx.min(),
        end_date=idx.max(),
        data_dir=str(data_dir),
        download_fn=lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("should not download")
        ),
    )

    assert downloaded is False
    assert warning is None
    assert "Close" in downloaded_df.columns


def test_get_ticker_data_downloads_when_cache_missing(tmp_path) -> None:
    data_dir = tmp_path / "data"
    idx = pd.date_range("2024-01-01", periods=5, freq="D")

    def fake_download(*args, **kwargs):
        return pd.DataFrame({"Close": [100, 101, 102, 103, 104]}, index=idx)

    downloaded_df, downloaded, warning = get_ticker_data(
        ticker="MSFT",
        start_date=idx.min(),
        end_date=idx.max(),
        data_dir=str(data_dir),
        download_fn=fake_download,
    )

    assert downloaded is True
    assert warning is None
    assert not downloaded_df.empty
    assert (data_dir / "MSFT_10y.csv").exists()


def test_add_return_features_adds_numeric_close_and_return() -> None:
    df = pd.DataFrame({"Close": [100, 102, 101]})
    result = add_return_features(df)
    assert "Return" in result.columns
    assert result["Close"].dtype.kind in {"i", "u", "f"}
    assert result["Return"].isna().sum() == 1


def test_get_ticker_data_handles_corrupt_cache_and_downloads(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_path = data_dir / "AAPL_10y.csv"
    csv_path.write_text("corrupt csv")
    idx = pd.date_range("2024-01-01", periods=3, freq="D")

    def fake_load_cached(*args, **kwargs):
        raise ValueError("cache parse error")

    def fake_download(*args, **kwargs):
        return pd.DataFrame({"Close": [10, 11, 12]}, index=idx)

    monkeypatch.setattr(market_data_service, "load_cached_ticker_data", fake_load_cached)

    downloaded_df, downloaded, warning = get_ticker_data(
        ticker="AAPL",
        start_date=idx.min(),
        end_date=idx.max(),
        data_dir=str(data_dir),
        download_fn=fake_download,
    )

    assert downloaded is True
    assert warning is None
    assert not downloaded_df.empty


def test_get_ticker_data_returns_warning_for_empty_download(tmp_path) -> None:
    data_dir = tmp_path / "data"

    def fake_download(*args, **kwargs):
        return pd.DataFrame()

    downloaded_df, downloaded, warning = get_ticker_data(
        ticker="TSLA",
        start_date="2024-01-01",
        end_date="2024-01-10",
        data_dir=str(data_dir),
        download_fn=fake_download,
    )

    assert downloaded is True
    assert downloaded_df.empty
    assert warning == "No data found for TSLA in selected date range."


def test_covers_date_range_returns_false_for_empty_dataframe() -> None:
    assert (
        market_data_service._covers_date_range(pd.DataFrame(), "2024-01-01", "2024-01-10") is False
    )


def test_add_return_features_handles_duplicate_close_columns() -> None:
    df = pd.DataFrame([[100, 101], [102, 103]], columns=["Close", "Close"])
    result = add_return_features(df)
    assert "Return" in result.columns


def test_get_ticker_data_uses_memory_cache_after_first_call(tmp_path) -> None:
    data_dir = tmp_path / "data"
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    calls = {"count": 0}

    def fake_download(*args, **kwargs):
        calls["count"] += 1
        return pd.DataFrame({"Close": [100, 101, 102, 103, 104]}, index=idx)

    first_df, first_downloaded, _ = get_ticker_data(
        ticker="QQQ",
        start_date=idx.min(),
        end_date=idx.max(),
        data_dir=str(data_dir),
        download_fn=fake_download,
    )
    second_df, second_downloaded, _ = get_ticker_data(
        ticker="QQQ",
        start_date=idx.min(),
        end_date=idx.max(),
        data_dir=str(data_dir),
        download_fn=fake_download,
    )

    assert first_downloaded is True
    assert second_downloaded is False
    assert calls["count"] == 1
    assert not first_df.empty
    assert not second_df.empty
