from __future__ import annotations

import numpy as np
import pandas as pd


def _validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")
    return df.copy()


def sma(series: pd.Series, window: int = 20) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def ema(series: pd.Series, span: int = 20) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(close, span=fast) - ema(close, span=slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame({"MACD": macd_line, "MACD_Signal": signal_line, "MACD_Hist": hist})


def bollinger_bands(close: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.DataFrame:
    mid = sma(close, window=window)
    std = close.rolling(window=window, min_periods=1).std()
    upper = mid + n_std * std
    lower = mid - n_std * std
    return pd.DataFrame({"BB_Mid": mid, "BB_Upper": upper, "BB_Lower": lower})


def vwap(df: pd.DataFrame) -> pd.Series:
    checked = _validate_ohlcv(df)
    typical_price = (checked["High"] + checked["Low"] + checked["Close"]) / 3
    cumulative_value = (typical_price * checked["Volume"]).cumsum()
    cumulative_volume = checked["Volume"].replace(0, np.nan).cumsum()
    return cumulative_value / cumulative_volume


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    checked = _validate_ohlcv(df)
    high_low = checked["High"] - checked["Low"]
    high_close = (checked["High"] - checked["Close"].shift(1)).abs()
    low_close = (checked["Low"] - checked["Close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()


def adx(df: pd.DataFrame, window: int = 14) -> pd.Series:
    checked = _validate_ohlcv(df)
    up_move = checked["High"].diff()
    down_move = -checked["Low"].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = atr(checked, window=window) * window
    plus_di = (
        100
        * pd.Series(plus_dm, index=checked.index).ewm(alpha=1 / window, adjust=False).mean()
        / tr
    )
    minus_di = (
        100
        * pd.Series(minus_dm, index=checked.index).ewm(alpha=1 / window, adjust=False).mean()
        / tr
    )
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)) * 100
    return dx.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()


def ichimoku_cloud(df: pd.DataFrame) -> pd.DataFrame:
    checked = _validate_ohlcv(df)
    conv = (checked["High"].rolling(9).max() + checked["Low"].rolling(9).min()) / 2
    base = (checked["High"].rolling(26).max() + checked["Low"].rolling(26).min()) / 2
    span_a = ((conv + base) / 2).shift(26)
    span_b = ((checked["High"].rolling(52).max() + checked["Low"].rolling(52).min()) / 2).shift(26)
    lagging = checked["Close"].shift(-26)
    return pd.DataFrame(
        {
            "ICHI_Conversion": conv,
            "ICHI_Base": base,
            "ICHI_SpanA": span_a,
            "ICHI_SpanB": span_b,
            "ICHI_Lagging": lagging,
        }
    )


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff().fillna(0.0))
    return (direction * volume).cumsum()


def stochastic_oscillator(df: pd.DataFrame, k_window: int = 14, d_window: int = 3) -> pd.DataFrame:
    checked = _validate_ohlcv(df)
    lowest_low = checked["Low"].rolling(k_window, min_periods=1).min()
    highest_high = checked["High"].rolling(k_window, min_periods=1).max()
    k = 100 * (checked["Close"] - lowest_low) / (highest_high - lowest_low).replace(0.0, np.nan)
    d = k.rolling(d_window, min_periods=1).mean()
    return pd.DataFrame({"STOCH_K": k, "STOCH_D": d})


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    checked = _validate_ohlcv(df)
    out = checked.copy()
    out["SMA_20"] = sma(out["Close"], window=20)
    out["EMA_20"] = ema(out["Close"], span=20)
    out["RSI_14"] = rsi(out["Close"], window=14)
    out = out.join(macd(out["Close"]))
    out = out.join(bollinger_bands(out["Close"], window=20, n_std=2.0))
    out["VWAP"] = vwap(out)
    out["ATR_14"] = atr(out, window=14)
    out["ADX_14"] = adx(out, window=14)
    out = out.join(ichimoku_cloud(out))
    out["OBV"] = obv(out["Close"], out["Volume"])
    out = out.join(stochastic_oscillator(out))
    return out
