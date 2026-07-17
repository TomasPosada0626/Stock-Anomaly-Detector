from typing import Optional

import numpy as np
import pandas as pd
from pandas import Series
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM


def detect_anomalies_zscore(returns: Series, threshold: float = 3) -> Series:
    """
    Detect anomalies in a pandas Series using the Z-Score method.

    Parameters:
        returns (pd.Series): Series of returns or values to analyze.
        threshold (float): Number of standard deviations to use as the anomaly cutoff.

    Returns:
        pd.Series: Boolean Series where True indicates an anomaly.
    """
    mean = returns.mean()
    std = returns.std()
    # An anomaly is any value more than 'threshold' std deviations from the mean
    return np.abs(returns - mean) > threshold * std


def detect_anomalies_iforest(
    returns: Series, contamination: float = 0.01, random_state: Optional[int] = 42
) -> Series:
    """
    Detect anomalies in a pandas Series using the Isolation Forest algorithm.

    Parameters:
        returns (pd.Series): Series of returns or values to analyze.
        contamination (float): The proportion of outliers in the data set.
        random_state (Optional[int]): Random seed for reproducibility.

    Returns:
        pd.Series: Boolean Series where True indicates an anomaly.
    """
    mask = returns.notna()
    iso = IsolationForest(contamination=contamination, random_state=random_state)
    preds = iso.fit_predict(returns[mask].values.reshape(-1, 1))
    result = pd.Series(False, index=returns.index)
    # Mark as anomaly where prediction is -1
    result[mask] = preds == -1
    return result


def detect_anomalies_lof(
    returns: Series, contamination: float = 0.01, n_neighbors: int = 20
) -> Series:
    """
    Detect anomalies in a pandas Series using Local Outlier Factor.

    Parameters:
        returns (pd.Series): Series of returns or values to analyze.
        contamination (float): Expected outlier proportion.
        n_neighbors (int): Number of neighbors used by LOF.

    Returns:
        pd.Series: Boolean Series where True indicates an anomaly.
    """
    mask = returns.notna()
    clean = returns[mask]
    result = pd.Series(False, index=returns.index)
    if clean.empty or len(clean) < 3:
        return result
    # LOF requires n_neighbors < n_samples.
    safe_neighbors = min(max(2, n_neighbors), len(clean) - 1)
    lof = LocalOutlierFactor(n_neighbors=safe_neighbors, contamination=contamination)
    preds = lof.fit_predict(clean.values.reshape(-1, 1))
    result[mask] = preds == -1
    return result


def detect_anomalies_one_class_svm(
    returns: Series, nu: float = 0.05, gamma: str = "scale"
) -> Series:
    """
    Detect anomalies in a pandas Series using One-Class SVM.

    Parameters:
        returns (pd.Series): Series of returns or values to analyze.
        nu (float): Upper bound on the fraction of anomalies.
        gamma (str): Kernel coefficient.

    Returns:
        pd.Series: Boolean Series where True indicates an anomaly.
    """
    mask = returns.notna()
    clean = returns[mask]
    result = pd.Series(False, index=returns.index)
    if clean.empty or len(clean) < 3:
        return result
    model = OneClassSVM(nu=nu, gamma=gamma)
    preds = model.fit_predict(clean.values.reshape(-1, 1))
    result[mask] = preds == -1
    return result
