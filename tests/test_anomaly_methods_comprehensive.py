import sys
from types import ModuleType

import pandas as pd

if "prophet" not in sys.modules:
    fake_prophet = ModuleType("prophet")

    class _BootstrapProphet:
        def __init__(self, *args, **kwargs):
            pass

        def fit(self, _df):
            return self

        def make_future_dataframe(self, periods: int = 0):
            return pd.DataFrame({"ds": [] if periods == 0 else [0] * periods})

        def predict(self, future):
            return pd.DataFrame({"yhat": [0.0] * len(future)})

    fake_prophet.Prophet = _BootstrapProphet
    sys.modules["prophet"] = fake_prophet

from services.anomaly_lab_service import run_anomaly_methods


class _FakeProphet:
    def __init__(self, daily_seasonality: bool = True) -> None:
        self.daily_seasonality = daily_seasonality
        self._fit_rows = 0

    def fit(self, df: pd.DataFrame):
        self._fit_rows = len(df)
        return self

    def make_future_dataframe(self, periods: int = 0) -> pd.DataFrame:
        return pd.DataFrame({"ds": range(self._fit_rows + periods)})

    def predict(self, future: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({"yhat": [100.0] * len(future)})


def test_run_anomaly_methods_all_seven_methods(monkeypatch) -> None:
    monkeypatch.setattr("services.anomaly_lab_service.Prophet", _FakeProphet)

    idx = pd.date_range("2026-01-01", periods=80, freq="D")
    close = pd.Series([100 + (i * 0.3) for i in range(80)], index=idx)
    close.iloc[20] = 140
    close.iloc[60] = 70
    returns = close.pct_change().fillna(0)
    df = pd.DataFrame({"Close": close, "Return": returns}, index=idx)

    selected_methods = [
        "Z-Score",
        "I-Forest",
        "DBSCAN",
        "Prophet",
        "Rolling Quantile",
        "LOF",
        "One-Class SVM",
    ]

    modeled, points, benchmark = run_anomaly_methods(
        df=df,
        selected_methods=selected_methods,
        zscore_threshold=2.5,
        iforest_contamination=0.05,
        dbscan_eps=0.08,
        dbscan_min_samples=4,
        rolling_window=20,
        quantile_low=0.05,
        quantile_high=0.95,
        lof_neighbors=10,
        ocsvm_nu=0.05,
    )

    expected_columns = {
        "Anomaly_zscore",
        "Anomaly_iforest",
        "Anomaly_dbscan",
        "Anomaly_prophet",
        "Anomaly_rolling_quantile",
        "Anomaly_lof",
        "Anomaly_ocsvm",
    }
    assert expected_columns.issubset(set(modeled.columns))
    assert set(benchmark["Method"]) == set(selected_methods)
    assert isinstance(points, pd.DataFrame)
    assert "Method" in points.columns
