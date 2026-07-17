from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _clean_returns(returns: pd.Series) -> pd.Series:
    return returns.replace([np.inf, -np.inf], np.nan).dropna()


def volatility(returns: pd.Series, annualization_factor: int = TRADING_DAYS) -> float:
    clean = _clean_returns(returns)
    if clean.empty:
        return 0.0
    return float(clean.std(ddof=0) * np.sqrt(annualization_factor))


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    clean = _clean_returns(returns)
    if clean.empty:
        return 0.0
    excess = clean - (risk_free_rate / TRADING_DAYS)
    std = excess.std(ddof=0)
    if std == 0:
        return 0.0
    return float((excess.mean() / std) * np.sqrt(TRADING_DAYS))


def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    clean = _clean_returns(returns)
    if clean.empty:
        return 0.0
    excess = clean - (risk_free_rate / TRADING_DAYS)
    downside = excess[excess < 0]
    downside_std = downside.std(ddof=0)
    if downside_std == 0 or np.isnan(downside_std):
        return 0.0
    return float((excess.mean() / downside_std) * np.sqrt(TRADING_DAYS))


def max_drawdown(equity_curve: pd.Series) -> float:
    clean = equity_curve.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    peak = clean.cummax()
    drawdown = (clean - peak) / peak.replace(0.0, np.nan)
    return float(drawdown.min())


def beta_alpha(asset_returns: pd.Series, benchmark_returns: pd.Series) -> tuple[float, float]:
    asset = _clean_returns(asset_returns)
    bench = _clean_returns(benchmark_returns)
    aligned = pd.concat([asset, bench], axis=1).dropna()
    if aligned.empty:
        return 0.0, 0.0
    cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1], ddof=0)
    var_bench = cov[1, 1]
    if var_bench == 0:
        return 0.0, 0.0
    beta = cov[0, 1] / var_bench
    alpha = aligned.iloc[:, 0].mean() - beta * aligned.iloc[:, 1].mean()
    return float(beta), float(alpha * TRADING_DAYS)


def correlation(asset_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    aligned = pd.concat([_clean_returns(asset_returns), _clean_returns(benchmark_returns)], axis=1)
    aligned = aligned.dropna()
    if aligned.empty:
        return 0.0
    corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
    return 0.0 if np.isnan(corr) else float(corr)


def value_at_risk(returns: pd.Series, confidence_level: float = 0.95) -> float:
    clean = _clean_returns(returns)
    if clean.empty:
        return 0.0
    tail_q = 1 - confidence_level
    return float(clean.quantile(tail_q))


def summarize_risk(
    asset_returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:
    benchmark = benchmark_returns if benchmark_returns is not None else pd.Series(dtype=float)
    beta, alpha = (0.0, 0.0)
    corr = 0.0
    if not benchmark.empty:
        beta, alpha = beta_alpha(asset_returns, benchmark)
        corr = correlation(asset_returns, benchmark)

    equity_curve = (1 + _clean_returns(asset_returns)).cumprod()
    return {
        "Sharpe Ratio": sharpe_ratio(asset_returns, risk_free_rate=risk_free_rate),
        "Sortino Ratio": sortino_ratio(asset_returns, risk_free_rate=risk_free_rate),
        "Maximum Drawdown": max_drawdown(equity_curve),
        "Volatility": volatility(asset_returns),
        "Beta": beta,
        "Alpha": alpha,
        "Correlation": corr,
        "VaR 95%": value_at_risk(asset_returns, confidence_level=0.95),
    }
