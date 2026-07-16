import pandas as pd


def rolling_quantile_anomaly(
    series: pd.Series, window: int = 20, quantile: float = 0.99
) -> pd.Series:
    """
    Detect anomalies using rolling quantile method.
    An anomaly is a value above the rolling quantile threshold.

    Parameters:
        series (pd.Series): Input data series.
        window (int): Rolling window size.
        quantile (float): Quantile threshold (e.g., 0.99 for top 1%).

    Returns:
        pd.Series: Boolean series where True indicates an anomaly.
    """
    threshold = series.rolling(window=window, min_periods=1).quantile(quantile)
    return series > threshold
