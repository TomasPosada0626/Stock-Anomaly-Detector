import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from services.indicators_service import add_indicators


def test_add_indicators_adds_expected_columns() -> None:
    idx = pd.date_range("2025-01-01", periods=120, freq="D")
    df = pd.DataFrame(
        {
            "Open": range(120),
            "High": [x + 2 for x in range(120)],
            "Low": [max(0, x - 2) for x in range(120)],
            "Close": [x + 1 for x in range(120)],
            "Volume": [1000 + x * 10 for x in range(120)],
        },
        index=idx,
    )

    result = add_indicators(df)

    expected = {
        "SMA_20",
        "EMA_20",
        "RSI_14",
        "MACD",
        "MACD_Signal",
        "MACD_Hist",
        "BB_Mid",
        "BB_Upper",
        "BB_Lower",
        "VWAP",
        "ATR_14",
        "ADX_14",
        "ICHI_Conversion",
        "ICHI_Base",
        "ICHI_SpanA",
        "ICHI_SpanB",
        "ICHI_Lagging",
        "OBV",
        "STOCH_K",
        "STOCH_D",
    }
    assert expected.issubset(result.columns)
