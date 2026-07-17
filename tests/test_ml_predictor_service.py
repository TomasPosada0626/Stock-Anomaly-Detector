import pandas as pd

from services.ml_predictor_service import MLPredictorService


def test_ml_predictor_predict_next_close() -> None:
    service = MLPredictorService()
    prices = pd.Series([100, 101, 102, 103, 104, 105, 106])
    result = service.predict_next_close(prices, horizon=2)

    assert "predicted_close" in result
    assert result["horizon"] == 2


def test_ml_predictor_detect_factor_drift() -> None:
    service = MLPredictorService()
    base = [0.01] * 100
    recent = [0.08] * 30
    series = pd.Series(base + recent)

    drift = service.detect_factor_drift(series, recent_window=30, baseline_window=90, threshold_std=1.0)
    assert drift["drift_detected"] is True
