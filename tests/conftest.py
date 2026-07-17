import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


@pytest.fixture
def sample_returns_series() -> pd.Series:
    return pd.Series([0.01, 0.02, 0.015, -0.01, 0.03, -0.02, 0.01])


@pytest.fixture
def returns_with_nans() -> pd.Series:
    return pd.Series([0.01, np.nan, 0.02, np.nan, -0.03, 0.01, 0.0])


@pytest.fixture
def empty_returns_series() -> pd.Series:
    return pd.Series(dtype=float)


@pytest.fixture
def large_returns_series() -> pd.Series:
    rng = np.random.default_rng(42)
    values = rng.normal(0.0, 0.02, size=10_000)
    values[123] = 0.45
    values[999] = -0.4
    values[7777] = 0.5
    return pd.Series(values)
