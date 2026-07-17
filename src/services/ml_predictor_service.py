from __future__ import annotations

import numpy as np
import pandas as pd


class MLPredictorService:
    def predict_next_close(
        self,
        prices: pd.Series,
        horizon: int = 1,
    ) -> dict[str, float | int]:
        clean = pd.to_numeric(prices, errors="coerce").dropna()
        if len(clean) < 5:
            raise ValueError("insufficient data for prediction")

        x = np.arange(len(clean), dtype=float)
        y = clean.to_numpy(dtype=float)
        slope, intercept = np.polyfit(x, y, 1)

        future_x = len(clean) - 1 + max(1, int(horizon))
        prediction = slope * future_x + intercept
        current = float(y[-1])
        delta_pct = ((float(prediction) / current) - 1) * 100 if current else 0.0

        return {
            "current_close": current,
            "predicted_close": float(prediction),
            "expected_change_pct": float(delta_pct),
            "horizon": int(max(1, int(horizon))),
        }

    def detect_factor_drift(
        self,
        series: pd.Series,
        recent_window: int = 30,
        baseline_window: int = 90,
        threshold_std: float = 2.0,
    ) -> dict[str, float | bool]:
        clean = pd.to_numeric(series, errors="coerce").dropna()
        total_window = int(recent_window) + int(baseline_window)
        if len(clean) < max(10, total_window):
            raise ValueError("insufficient data for drift detection")

        recent = clean.tail(int(recent_window))
        baseline = clean.tail(total_window).head(int(baseline_window))

        baseline_mean = float(baseline.mean())
        baseline_std = float(baseline.std(ddof=0))
        recent_mean = float(recent.mean())
        z_score = 0.0 if baseline_std == 0 else (recent_mean - baseline_mean) / baseline_std

        return {
            "recent_mean": recent_mean,
            "baseline_mean": baseline_mean,
            "baseline_std": baseline_std,
            "z_score": float(z_score),
            "drift_detected": bool(abs(z_score) >= float(threshold_std)),
        }
