from __future__ import annotations

from datetime import datetime
from typing import Dict

import pandas as pd

from anomaly_methods import detect_anomalies_iforest, detect_anomalies_zscore
from services.alerts_service import AlertRule, AlertsService
from services.auth_service import AuthService
from services.backtesting_service import BacktestingService, StrategyRules
from services.health_service import HealthService
from services.indicators_service import add_indicators
from services.market_data_service import add_return_features, get_ticker_data
from services.observability import get_metrics_snapshot
from services.portfolio_service import PortfolioService, PositionInput
from services.reports_service import ReportsService
from services.watchlist_service import WatchlistInput, WatchlistService

try:
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover - optional dependency
    BaseModel = object  # type: ignore[assignment]

    def Field(*args, **kwargs):  # type: ignore[override]
        return None


try:
    from fastapi import FastAPI, HTTPException
except Exception:  # pragma: no cover - optional dependency
    FastAPI = None  # type: ignore[assignment]
    HTTPException = Exception  # type: ignore[assignment]


def parse_prices(raw: str) -> Dict[str, float]:
    if not raw.strip():
        return {}
    prices: Dict[str, float] = {}
    for token in raw.split(","):
        if ":" not in token:
            continue
        ticker, value = token.split(":", 1)
        ticker_clean = ticker.strip().upper()
        try:
            prices[ticker_clean] = float(value.strip())
        except ValueError:
            continue
    return prices


class PortfolioPositionCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    quantity: float = Field(gt=0)
    buy_price: float = Field(gt=0)
    buy_date: str


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WatchlistItemCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)


class AlertRuleCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    alert_type: str = Field(min_length=1, max_length=60)
    threshold: float | None = None
    active: bool = True


def create_app(
    auth_service: AuthService | None = None,
    portfolio_service: PortfolioService | None = None,
    alerts_service: AlertsService | None = None,
    watchlist_service: WatchlistService | None = None,
    reports_service: ReportsService | None = None,
    backtesting_service: BacktestingService | None = None,
):
    if FastAPI is None:
        raise RuntimeError(
            "FastAPI is not installed. Add fastapi and uvicorn to run the API layer."
        )

    auth = auth_service or AuthService()
    portfolio = portfolio_service or PortfolioService()
    alerts = alerts_service or AlertsService()
    watchlists = watchlist_service or WatchlistService()
    reports = reports_service or ReportsService()
    backtesting = backtesting_service or BacktestingService()
    health_service = HealthService()

    app = FastAPI(title="QuantVision API", version="1.0.0")

    def _route(method: str, path: str):
        decorator = getattr(app, method, None)
        if decorator is None:
            decorator = app.get
        return decorator(path)

    def _authorize_module(username: str, module_name: str) -> None:
        if not auth.can_access_module(username, module_name):
            raise HTTPException(
                status_code=403, detail=f"forbidden: role cannot access {module_name}"
            )

    @_route("get", "/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "quantvision-api"}

    @_route("get", "/health/detailed")
    def health_detailed() -> dict[str, object]:
        return health_service.run_checks()

    @_route("get", "/metrics")
    def metrics_snapshot() -> dict[str, object]:
        return get_metrics_snapshot()

    @_route("get", "/users/{username}/role")
    def user_role(username: str) -> dict[str, str]:
        return {"username": username, "role": auth.get_user_role(username)}

    @_route("get", "/users/{username}/portfolio/summary")
    def portfolio_summary(username: str, prices: str = "") -> dict[str, float]:
        _authorize_module(username, "Portfolio")
        price_map = parse_prices(prices)
        return portfolio.compute_portfolio_metrics(username, latest_prices=price_map)

    @_route("get", "/users/{username}/portfolio/positions")
    def portfolio_positions(username: str):
        _authorize_module(username, "Portfolio")
        frame = portfolio.list_positions(username)
        return frame.to_dict(orient="records")

    @_route("post", "/users/{username}/portfolio/positions")
    def portfolio_positions_create(username: str, payload: PortfolioPositionCreate):
        _authorize_module(username, "Portfolio")
        position_id = portfolio.add_position(
            PositionInput(
                username=username,
                ticker=payload.ticker,
                quantity=payload.quantity,
                buy_price=payload.buy_price,
                buy_date=payload.buy_date,
            )
        )
        return {"id": int(position_id)}

    @_route("delete", "/users/{username}/portfolio/positions/{position_id}")
    def portfolio_positions_delete(username: str, position_id: int):
        _authorize_module(username, "Portfolio")
        portfolio.remove_position(position_id=position_id, username=username)
        return {"deleted": True, "id": int(position_id)}

    @_route("get", "/users/{username}/alerts/history")
    def alerts_history(username: str, limit: int = 100):
        _authorize_module(username, "Alerts")
        if limit <= 0:
            raise HTTPException(status_code=400, detail="limit must be positive")
        frame = alerts.list_history(username, limit=limit)
        return frame.to_dict(orient="records")

    @_route("get", "/users/{username}/alerts/rules")
    def alerts_rules(username: str):
        _authorize_module(username, "Alerts")
        frame = alerts.list_rules(username)
        return frame.to_dict(orient="records")

    @_route("post", "/users/{username}/alerts/rules")
    def alerts_rules_create(username: str, payload: AlertRuleCreate):
        _authorize_module(username, "Alerts")
        rule_id = alerts.create_rule(
            AlertRule(
                username=username,
                ticker=payload.ticker,
                alert_type=payload.alert_type,
                threshold=payload.threshold,
                active=payload.active,
            )
        )
        return {"id": int(rule_id)}

    @_route("delete", "/users/{username}/alerts/rules/{rule_id}")
    def alerts_rules_delete(username: str, rule_id: int):
        _authorize_module(username, "Alerts")
        alerts.delete_rule(rule_id=rule_id, username=username)
        return {"deleted": True, "id": int(rule_id)}

    @_route("get", "/users/{username}/watchlists")
    def user_watchlists(username: str):
        _authorize_module(username, "Watchlists")
        frame = watchlists.list_watchlists(username)
        return frame.to_dict(orient="records")

    @_route("post", "/users/{username}/watchlists")
    def user_watchlists_create(username: str, payload: WatchlistCreate):
        _authorize_module(username, "Watchlists")
        watchlist_id = watchlists.create_watchlist(
            WatchlistInput(username=username, name=payload.name)
        )
        return {"id": int(watchlist_id)}

    @_route("delete", "/users/{username}/watchlists/{watchlist_id}")
    def user_watchlists_delete(username: str, watchlist_id: int):
        _authorize_module(username, "Watchlists")
        watchlists.delete_watchlist(watchlist_id=watchlist_id, username=username)
        return {"deleted": True, "id": int(watchlist_id)}

    @_route("get", "/users/{username}/watchlists/{watchlist_id}/items")
    def user_watchlist_items(username: str, watchlist_id: int):
        _authorize_module(username, "Watchlists")
        existing = watchlists.list_watchlists(username)
        if watchlist_id not in existing.get("id", pd.Series(dtype=int)).tolist():
            raise HTTPException(status_code=404, detail="watchlist not found")
        frame = watchlists.list_items(watchlist_id)
        return frame.to_dict(orient="records")

    @_route("post", "/users/{username}/watchlists/{watchlist_id}/items")
    def user_watchlist_items_create(username: str, watchlist_id: int, payload: WatchlistItemCreate):
        _authorize_module(username, "Watchlists")
        existing = watchlists.list_watchlists(username)
        if watchlist_id not in existing.get("id", pd.Series(dtype=int)).tolist():
            raise HTTPException(status_code=404, detail="watchlist not found")
        watchlists.add_ticker(watchlist_id=watchlist_id, ticker=payload.ticker)
        return {"added": True, "ticker": payload.ticker.upper()}

    @_route("delete", "/users/{username}/watchlists/{watchlist_id}/items/{ticker}")
    def user_watchlist_items_delete(username: str, watchlist_id: int, ticker: str):
        _authorize_module(username, "Watchlists")
        existing = watchlists.list_watchlists(username)
        if watchlist_id not in existing.get("id", pd.Series(dtype=int)).tolist():
            raise HTTPException(status_code=404, detail="watchlist not found")
        watchlists.remove_ticker(watchlist_id=watchlist_id, ticker=ticker)
        return {"deleted": True, "ticker": ticker.upper()}

    @_route("get", "/analytics/{ticker}/indicators")
    def ticker_indicators(ticker: str, start: str = "2019-01-01", end: str = ""):
        end_date = end or datetime.today().strftime("%Y-%m-%d")
        df, _, warning = get_ticker_data(ticker=ticker.upper(), start_date=start, end_date=end_date)
        if warning:
            raise HTTPException(status_code=404, detail=warning)
        if df.empty:
            raise HTTPException(status_code=404, detail="no data")
        prepared = add_indicators(add_return_features(df))
        latest = prepared.iloc[-1].to_dict()
        return {"ticker": ticker.upper(), "indicators": latest}

    @_route("get", "/analytics/{ticker}/anomalies")
    def ticker_anomalies(
        ticker: str,
        start: str = "2019-01-01",
        end: str = "",
        zscore_threshold: float = 3.0,
        contamination: float = 0.01,
    ):
        end_date = end or datetime.today().strftime("%Y-%m-%d")
        df, _, warning = get_ticker_data(ticker=ticker.upper(), start_date=start, end_date=end_date)
        if warning:
            raise HTTPException(status_code=404, detail=warning)
        if df.empty:
            raise HTTPException(status_code=404, detail="no data")
        prepared = add_return_features(df)
        z_mask = detect_anomalies_zscore(prepared["Return"], threshold=zscore_threshold)
        i_mask = detect_anomalies_iforest(prepared["Return"], contamination=contamination)
        return {
            "ticker": ticker.upper(),
            "zscore_count": int(z_mask.sum()),
            "iforest_count": int(i_mask.sum()),
        }

    @_route("get", "/analytics/{ticker}/backtest")
    def ticker_backtest(ticker: str, start: str = "2019-01-01", end: str = ""):
        end_date = end or datetime.today().strftime("%Y-%m-%d")
        df, _, warning = get_ticker_data(ticker=ticker.upper(), start_date=start, end_date=end_date)
        if warning:
            raise HTTPException(status_code=404, detail=warning)
        if df.empty:
            raise HTTPException(status_code=404, detail="no data")
        prepared = add_indicators(add_return_features(df))
        rules = StrategyRules(
            buy_condition=lambda row, prev: bool(row.get("RSI_14", 50) < 30),
            sell_condition=lambda row, prev: bool(row.get("RSI_14", 50) > 70),
            take_profit_pct=5.0,
        )
        result = backtesting.run_rule_based_strategy(prepared, rules=rules)
        trade_log = result.get("Trade Log", [])
        trimmed = trade_log[-10:] if isinstance(trade_log, list) else []
        result["Trade Log"] = trimmed
        return result

    @_route("get", "/users/{username}/reports/portfolio")
    def portfolio_report(username: str, prices: str = ""):
        _authorize_module(username, "Reports")
        summary = portfolio.compute_portfolio_metrics(username, latest_prices=parse_prices(prices))
        positions = portfolio.list_positions(username)
        pdf = reports.build_portfolio_report(
            title=f"QuantVision Portfolio Report | {username}",
            portfolio_metrics=summary,
            positions=positions,
        )
        return {
            "username": username,
            "summary": summary,
            "positions": positions.to_dict(orient="records"),
            "pdf_bytes": len(pdf),
        }

    return app
