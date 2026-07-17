import time

import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.cluster import DBSCAN

from anomaly_methods import (
    detect_anomalies_iforest,
    detect_anomalies_lof,
    detect_anomalies_one_class_svm,
    detect_anomalies_zscore,
)
from observability.metrics import record_anomalies_detected, record_method_runtime
from services.observability import get_logger

logger = get_logger("anomaly_lab_service")


def run_anomaly_methods(
    df: pd.DataFrame,
    selected_methods: list[str],
    zscore_threshold: float,
    iforest_contamination: float,
    dbscan_eps: float,
    dbscan_min_samples: int,
    rolling_window: int,
    quantile_low: float,
    quantile_high: float,
    lof_neighbors: int,
    ocsvm_nu: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    model_df = df.copy()
    comparisons: list[dict[str, float | str]] = []
    method_labels: list[tuple[str, str]] = []

    for method in selected_methods:
        start = time.time()
        col_name = ""
        params: dict[str, float | int | str] = {}

        if method == "Z-Score":
            col_name = "Anomaly_zscore"
            model_df[col_name] = detect_anomalies_zscore(
                model_df["Return"], threshold=zscore_threshold
            )
            params = {"threshold": zscore_threshold}
        elif method == "I-Forest":
            col_name = "Anomaly_iforest"
            model_df[col_name] = detect_anomalies_iforest(
                model_df["Return"], contamination=iforest_contamination, random_state=42
            )
            params = {"contamination": iforest_contamination}
        elif method == "DBSCAN":
            col_name = "Anomaly_dbscan"
            mask = model_df["Return"].notna()
            model_df[col_name] = False
            values = model_df.loc[mask, ["Return"]].values.reshape(-1, 1)
            if len(values) > 0:
                dbscan = DBSCAN(eps=dbscan_eps, min_samples=dbscan_min_samples)
                model_df.loc[mask, col_name] = dbscan.fit_predict(values) == -1
            params = {"eps": dbscan_eps, "min_samples": dbscan_min_samples}
        elif method == "Prophet":
            col_name = "Anomaly_prophet"
            model_df[col_name] = False
            try:
                prophet_df = model_df[["Close"]].reset_index()
                prophet_df.columns = ["ds", "y"]
                prophet_df["ds"] = pd.to_datetime(prophet_df["ds"]).dt.tz_localize(None)
                model = Prophet(daily_seasonality=True)
                model.fit(prophet_df)
                forecast = model.predict(model.make_future_dataframe(periods=0))
                residuals = model_df["Close"].values - forecast["yhat"].values
                model_df[col_name] = np.abs(residuals) > 3 * np.std(residuals)
            except Exception as prophet_error:  # pragma: no cover - defensive logging
                logger.warning("prophet_failed error=%s", str(prophet_error))
            params = {"residual_threshold": 3.0}
        elif method == "Rolling Quantile":
            col_name = "Anomaly_rolling_quantile"
            lower = (
                model_df["Close"]
                .rolling(window=rolling_window, min_periods=1)
                .quantile(quantile_low)
            )
            upper = (
                model_df["Close"]
                .rolling(window=rolling_window, min_periods=1)
                .quantile(quantile_high)
            )
            model_df[col_name] = (model_df["Close"] < lower) | (model_df["Close"] > upper)
            params = {
                "window": rolling_window,
                "q_low": quantile_low,
                "q_high": quantile_high,
            }
        elif method == "LOF":
            col_name = "Anomaly_lof"
            model_df[col_name] = detect_anomalies_lof(
                model_df["Return"], contamination=iforest_contamination, n_neighbors=lof_neighbors
            )
            params = {"contamination": iforest_contamination, "n_neighbors": lof_neighbors}
        elif method == "One-Class SVM":
            col_name = "Anomaly_ocsvm"
            model_df[col_name] = detect_anomalies_one_class_svm(model_df["Return"], nu=ocsvm_nu)
            params = {"nu": ocsvm_nu}

        elapsed = time.time() - start
        if col_name:
            anomaly_count = int(model_df[col_name].sum())
            record_method_runtime(method=method, duration_seconds=elapsed)
            record_anomalies_detected(method=method, count=anomaly_count)
            method_labels.append((col_name, method))
            comparisons.append(
                {
                    "Method": method,
                    "Anomalies": anomaly_count,
                    "Time (s)": round(elapsed, 4),
                    "Parameters": str(params),
                }
            )

    anomaly_df = model_df.copy()
    anomaly_df["Method"] = "None"
    for col, label in method_labels:
        anomaly_df.loc[anomaly_df[col], "Method"] = label
    points = anomaly_df[anomaly_df["Method"] != "None"]
    benchmark = pd.DataFrame(comparisons)
    return model_df, points, benchmark
