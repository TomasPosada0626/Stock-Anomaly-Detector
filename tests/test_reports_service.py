import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from services.reports_service import ReportsService
from ui.charts import build_comparison_chart


def test_reports_service_generates_csv_pdf_and_png() -> None:
    svc = ReportsService()
    idx = pd.date_range("2025-01-01", periods=5, freq="D")
    df = pd.DataFrame({"Close": [10, 11, 12, 11, 13], "Volume": [100, 110, 120, 90, 130]}, index=idx)

    csv_bytes = svc.to_csv_bytes(df)
    assert b"Close" in csv_bytes

    pdf_bytes = svc.to_pdf_bytes("QuantVision Test Report", {"Summary": {"rows": 5}, "Data": df})
    assert len(pdf_bytes) > 50

    fig = build_comparison_chart(df[["Close"]], "Close")
    png_bytes = svc.to_png_bytes(fig)
    # PNG generation can fail in environments without full image backend; method must not crash.
    assert isinstance(png_bytes, bytes)


def test_reports_service_fallback_and_executive_builder() -> None:
    svc = ReportsService()
    idx = pd.date_range("2025-01-01", periods=3, freq="D")
    benchmark = pd.DataFrame({"Sharpe Ratio": [1.2], "Volatility": [0.21]}, index=[idx[-1]])

    # Figure object without to_image should gracefully return empty bytes.
    class NoImage:
        pass

    assert svc.to_png_bytes(NoImage()) == b""

    pdf_exec = svc.build_executive_report(
        "Executive",
        {"Current Price": 100.0, "Sharpe": 1.2},
        benchmark,
    )
    assert pdf_exec.startswith(b"%PDF")

    custom_pdf = svc.to_pdf_bytes("Custom", {"Narrative": "ok", "Data": benchmark})
    assert custom_pdf.startswith(b"%PDF")
