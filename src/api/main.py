from __future__ import annotations

from datetime import UTC, datetime
from typing import Dict

import pandas as pd

from analytics.event_tracker import AnalyticsEvent, EventTracker
from analytics.experimentation import ExperimentationService
from anomaly_methods import detect_anomalies_iforest, detect_anomalies_zscore
from integrations.webhooks import WebhookNotifier, WebhookPayload
from observability.tracing import initialize_tracing
from security.input_validation import require_ticker_whitelist, sanitize_ticker
from services.alerts_service import AlertRule, AlertsService
from services.auth_service import AuthService
from services.backtesting_service import BacktestingService, StrategyRules
from services.health_service import HealthService
from services.indicators_service import add_indicators
from services.market_data_service import add_return_features, get_ticker_data
from services.ml_predictor_service import MLPredictorService
from services.observability import get_metrics_snapshot, get_prometheus_metrics_text
from services.portfolio_service import PortfolioService, PositionInput
from services.reports_service import ReportsService
from services.strategy_governance_service import StrategyGovernanceService, StrategyProposal
from services.watchlist_service import WatchlistInput, WatchlistService

try:
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover - optional dependency
    BaseModel = object  # type: ignore[assignment]

    def Field(*args, **kwargs):  # type: ignore[override]
        return None


try:
    from fastapi import FastAPI, HTTPException, Request
except Exception:  # pragma: no cover - optional dependency
    FastAPI = None  # type: ignore[assignment]
    HTTPException = Exception  # type: ignore[assignment]
    Request = object  # type: ignore[assignment]

try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.extension import _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
except Exception:  # pragma: no cover - optional dependency
    Limiter = None  # type: ignore[assignment]
    RateLimitExceeded = Exception  # type: ignore[assignment]

    def _rate_limit_exceeded_handler(*args, **kwargs):  # type: ignore[override]
        return None

    def get_remote_address(request):  # type: ignore[override]
        return "unknown"


_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_REQUESTS = 10
_rate_limit_store: dict[str, list[datetime]] = {}


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


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=200)


class GovernanceProposalCreate(BaseModel):
    strategy_name: str = Field(min_length=1, max_length=120)
    created_by: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=5, max_length=1000)


class GovernanceDecisionRequest(BaseModel):
    approved_by: str = Field(min_length=1, max_length=120)


class WebhookDispatchRequest(BaseModel):
    url: str = Field(min_length=8, max_length=500)
    event: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=2000)
    source: str = Field(default="quantvision", min_length=1, max_length=120)


class ExperimentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    feature: str = Field(min_length=1, max_length=120)
    variants: list[str]
    hypothesis: str = Field(min_length=5, max_length=2000)


class ExperimentAssignmentRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)


class ExperimentConversionRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)


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
    event_tracker = EventTracker()
    experimentation = ExperimentationService()
    governance = StrategyGovernanceService()
    ml_predictor = MLPredictorService()
    webhook_notifier = WebhookNotifier()
    initialize_tracing(service_name="quantvision-api")
    allowed_tickers = {
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "TSLA",
        "META",
        "NVDA",
        "JPM",
        "V",
        "DIS",
    }

    app = FastAPI(title="QuantVision API", version="1.0.0")
    limiter = Limiter(key_func=get_remote_address) if Limiter is not None else None
    if limiter is not None and hasattr(app, "state"):
        app.state.limiter = limiter
    add_exception_handler = getattr(app, "add_exception_handler", None)
    if limiter is not None and callable(add_exception_handler):
        add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    middleware = getattr(app, "middleware", None)
    enable_rate_limit = callable(middleware)
    if callable(middleware):

        @app.middleware("http")
        async def _security_headers_middleware(request, call_next):
            response = await call_next(request)
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; frame-ancestors 'none'"
            )
            return response

    def _route(method: str, path: str):
        decorator = getattr(app, method, None)
        if decorator is None:
            decorator = app.get
        return decorator(path)

    def _limit(spec: str):
        if limiter is None:

            def _passthrough(func):
                return func

            return _passthrough
        return limiter.limit(spec)

    def _authorize_module(username: str, module_name: str) -> None:
        if not auth.can_access_module(username, module_name):
            raise HTTPException(
                status_code=403, detail=f"forbidden: role cannot access {module_name}"
            )

    def _enforce_rate_limit(subject: str) -> None:
        if not enable_rate_limit:
            return
        now = datetime.now(UTC)
        threshold = now.timestamp() - _RATE_LIMIT_WINDOW_SECONDS
        bucket = _rate_limit_store.setdefault(subject, [])
        bucket[:] = [item for item in bucket if item.timestamp() >= threshold]
        if len(bucket) >= _RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=429, detail="rate limit exceeded: 10 requests per minute"
            )
        bucket.append(now)

    def _require_authenticated_user(username: str, session_id: str) -> None:
        _enforce_rate_limit(f"user:{username}")
        validate_session_owner = getattr(auth, "validate_session_owner", None)
        if callable(validate_session_owner):
            if not validate_session_owner(session_id, username):
                raise HTTPException(
                    status_code=401, detail="unauthorized: invalid or expired session"
                )

    @_route("post", "/auth/login")
    @_limit("10/minute")
    def login(payload: LoginRequest, request: Request = None):
        _enforce_rate_limit(f"login:{payload.identifier.strip().lower()}")
        success, reason = auth.authenticate_user_with_reason(payload.identifier, payload.password)
        if not success:
            raise HTTPException(status_code=401, detail=reason or "invalid credentials")

        username = auth.get_username_by_identifier(payload.identifier)
        if not username:
            raise HTTPException(status_code=401, detail="invalid credentials")

        session_id = auth.create_session(username)
        event_tracker.track(
            AnalyticsEvent(
                username=username,
                feature="auth",
                event_name="login_success",
                metadata="api_login",
            )
        )
        return {
            "username": username,
            "role": auth.get_user_role(username),
            "session_id": session_id,
        }

    @_route("post", "/auth/logout")
    def logout(session_id: str = ""):
        if not session_id or not auth.is_session_valid(session_id):
            raise HTTPException(status_code=401, detail="unauthorized: invalid or expired session")
        auth.invalidate_session(session_id)
        return {"logged_out": True}

    @_route("get", "/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "quantvision-api"}

    @_route("get", "/health/detailed")
    def health_detailed() -> dict[str, object]:
        return health_service.run_checks()

    @_route("get", "/metrics")
    def metrics_snapshot() -> dict[str, object]:
        return get_metrics_snapshot()

    @_route("get", "/metrics/prometheus")
    def metrics_prometheus() -> str:
        return get_prometheus_metrics_text()

    @_route("get", "/analytics/usage/summary")
    def analytics_usage_summary(limit: int = 10) -> dict[str, object]:
        top_features = event_tracker.top_features(limit=max(1, int(limit)))
        return {
            "top_features": top_features.to_dict(orient="records"),
            "funnel": event_tracker.funnel(),
        }

    @_route("post", "/analytics/experiments")
    def analytics_create_experiment(payload: ExperimentCreateRequest) -> dict[str, str]:
        experimentation.create_experiment(
            name=payload.name,
            feature=payload.feature,
            variants=payload.variants,
            hypothesis=payload.hypothesis,
        )
        return {"name": payload.name, "status": "created"}

    @_route("get", "/analytics/experiments")
    def analytics_list_experiments(status: str = "") -> list[dict[str, object]]:
        frame = experimentation.list_experiments(status=status or None)
        return frame.to_dict(orient="records")

    @_route("post", "/analytics/experiments/{name}/assignment")
    def analytics_assign_experiment(
        name: str, payload: ExperimentAssignmentRequest
    ) -> dict[str, str]:
        variant = experimentation.assign_variant(name, payload.username)
        event_tracker.track(
            AnalyticsEvent(
                username=payload.username,
                feature="experimentation",
                event_name="ab_exposure",
                metadata=f"experiment={name};variant={variant}",
            )
        )
        return {"experiment": name, "username": payload.username, "variant": variant}

    @_route("post", "/analytics/experiments/{name}/conversion")
    def analytics_conversion_experiment(
        name: str, payload: ExperimentConversionRequest
    ) -> dict[str, object]:
        experimentation.track_conversion(name, payload.username)
        event_tracker.track(
            AnalyticsEvent(
                username=payload.username,
                feature="experimentation",
                event_name="ab_conversion",
                metadata=f"experiment={name}",
            )
        )
        return {"experiment": name, "username": payload.username, "converted": True}

    @_route("get", "/analytics/experiments/{name}/summary")
    def analytics_experiment_summary(name: str) -> list[dict[str, object]]:
        frame = experimentation.summary(name)
        return frame.to_dict(orient="records")

    @_route("get", "/users/{username}/role")
    def user_role(username: str, session_id: str = "") -> dict[str, str]:
        _require_authenticated_user(username, session_id)
        return {"username": username, "role": auth.get_user_role(username)}

    @_route("get", "/users/{username}/portfolio/summary")
    def portfolio_summary(
        username: str, prices: str = "", session_id: str = ""
    ) -> dict[str, float]:
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Portfolio")
        price_map = parse_prices(prices)
        return portfolio.compute_portfolio_metrics(username, latest_prices=price_map)

    @_route("get", "/users/{username}/portfolio/positions")
    def portfolio_positions(username: str, session_id: str = ""):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Portfolio")
        frame = portfolio.list_positions(username)
        return frame.to_dict(orient="records")

    @_route("post", "/users/{username}/portfolio/positions")
    def portfolio_positions_create(
        username: str, payload: PortfolioPositionCreate, session_id: str = ""
    ):
        _require_authenticated_user(username, session_id)
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
    def portfolio_positions_delete(username: str, position_id: int, session_id: str = ""):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Portfolio")
        portfolio.remove_position(position_id=position_id, username=username)
        return {"deleted": True, "id": int(position_id)}

    @_route("get", "/users/{username}/alerts/history")
    def alerts_history(username: str, limit: int = 100, session_id: str = ""):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Alerts")
        if limit <= 0:
            raise HTTPException(status_code=400, detail="limit must be positive")
        frame = alerts.list_history(username, limit=limit)
        return frame.to_dict(orient="records")

    @_route("get", "/users/{username}/alerts/rules")
    def alerts_rules(username: str, session_id: str = ""):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Alerts")
        frame = alerts.list_rules(username)
        return frame.to_dict(orient="records")

    @_route("post", "/users/{username}/alerts/rules")
    def alerts_rules_create(username: str, payload: AlertRuleCreate, session_id: str = ""):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Alerts")
        normalized_ticker = require_ticker_whitelist(payload.ticker, allowed=allowed_tickers)
        rule_id = alerts.create_rule(
            AlertRule(
                username=username,
                ticker=normalized_ticker,
                alert_type=payload.alert_type,
                threshold=payload.threshold,
                active=payload.active,
            )
        )
        return {"id": int(rule_id)}

    @_route("delete", "/users/{username}/alerts/rules/{rule_id}")
    def alerts_rules_delete(username: str, rule_id: int, session_id: str = ""):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Alerts")
        alerts.delete_rule(rule_id=rule_id, username=username)
        return {"deleted": True, "id": int(rule_id)}

    @_route("get", "/users/{username}/watchlists")
    def user_watchlists(username: str, session_id: str = ""):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Watchlists")
        frame = watchlists.list_watchlists(username)
        return frame.to_dict(orient="records")

    @_route("post", "/users/{username}/watchlists")
    def user_watchlists_create(username: str, payload: WatchlistCreate, session_id: str = ""):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Watchlists")
        watchlist_id = watchlists.create_watchlist(
            WatchlistInput(username=username, name=payload.name)
        )
        return {"id": int(watchlist_id)}

    @_route("delete", "/users/{username}/watchlists/{watchlist_id}")
    def user_watchlists_delete(username: str, watchlist_id: int, session_id: str = ""):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Watchlists")
        watchlists.delete_watchlist(watchlist_id=watchlist_id, username=username)
        return {"deleted": True, "id": int(watchlist_id)}

    @_route("get", "/users/{username}/watchlists/{watchlist_id}/items")
    def user_watchlist_items(username: str, watchlist_id: int, session_id: str = ""):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Watchlists")
        existing = watchlists.list_watchlists(username)
        if watchlist_id not in existing.get("id", pd.Series(dtype=int)).tolist():
            raise HTTPException(status_code=404, detail="watchlist not found")
        frame = watchlists.list_items(watchlist_id)
        return frame.to_dict(orient="records")

    @_route("post", "/users/{username}/watchlists/{watchlist_id}/items")
    def user_watchlist_items_create(
        username: str,
        watchlist_id: int,
        payload: WatchlistItemCreate,
        session_id: str = "",
    ):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Watchlists")
        existing = watchlists.list_watchlists(username)
        if watchlist_id not in existing.get("id", pd.Series(dtype=int)).tolist():
            raise HTTPException(status_code=404, detail="watchlist not found")
        try:
            ticker = require_ticker_whitelist(payload.ticker, allowed=allowed_tickers)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        watchlists.add_ticker(watchlist_id=watchlist_id, ticker=ticker)
        return {"added": True, "ticker": ticker}

    @_route("delete", "/users/{username}/watchlists/{watchlist_id}/items/{ticker}")
    def user_watchlist_items_delete(
        username: str, watchlist_id: int, ticker: str, session_id: str = ""
    ):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Watchlists")
        existing = watchlists.list_watchlists(username)
        if watchlist_id not in existing.get("id", pd.Series(dtype=int)).tolist():
            raise HTTPException(status_code=404, detail="watchlist not found")
        watchlists.remove_ticker(watchlist_id=watchlist_id, ticker=ticker)
        return {"deleted": True, "ticker": ticker.upper()}

    @_route("get", "/analytics/{ticker}/indicators")
    def ticker_indicators(ticker: str, start: str = "2019-01-01", end: str = ""):
        try:
            ticker = require_ticker_whitelist(ticker, allowed=allowed_tickers)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        end_date = end or datetime.today().strftime("%Y-%m-%d")
        df, _, warning = get_ticker_data(ticker=ticker, start_date=start, end_date=end_date)
        if warning:
            raise HTTPException(status_code=404, detail=warning)
        if df.empty:
            raise HTTPException(status_code=404, detail="no data")
        prepared = add_indicators(add_return_features(df))
        latest = prepared.iloc[-1].to_dict()
        return {"ticker": ticker, "indicators": latest}

    @_route("get", "/analytics/{ticker}/anomalies")
    def ticker_anomalies(
        ticker: str,
        start: str = "2019-01-01",
        end: str = "",
        zscore_threshold: float = 3.0,
        contamination: float = 0.01,
    ):
        try:
            ticker = require_ticker_whitelist(ticker, allowed=allowed_tickers)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        end_date = end or datetime.today().strftime("%Y-%m-%d")
        df, _, warning = get_ticker_data(ticker=ticker, start_date=start, end_date=end_date)
        if warning:
            raise HTTPException(status_code=404, detail=warning)
        if df.empty:
            raise HTTPException(status_code=404, detail="no data")
        prepared = add_return_features(df)
        z_mask = detect_anomalies_zscore(prepared["Return"], threshold=zscore_threshold)
        i_mask = detect_anomalies_iforest(prepared["Return"], contamination=contamination)
        event_tracker.track(
            AnalyticsEvent(
                username="anonymous",
                feature="anomalies",
                event_name="run_anomaly_methods",
                metadata=f"ticker={ticker}",
            )
        )
        return {
            "ticker": ticker,
            "zscore_count": int(z_mask.sum()),
            "iforest_count": int(i_mask.sum()),
        }

    @_route("get", "/analytics/{ticker}/backtest")
    def ticker_backtest(ticker: str, start: str = "2019-01-01", end: str = ""):
        try:
            ticker = sanitize_ticker(ticker)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        end_date = end or datetime.today().strftime("%Y-%m-%d")
        df, _, warning = get_ticker_data(ticker=ticker, start_date=start, end_date=end_date)
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

    @_route("get", "/analytics/{ticker}/ml-predict")
    def ticker_ml_predict(ticker: str, start: str = "2019-01-01", end: str = "", horizon: int = 1):
        try:
            ticker = sanitize_ticker(ticker)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        end_date = end or datetime.today().strftime("%Y-%m-%d")
        df, _, warning = get_ticker_data(ticker=ticker, start_date=start, end_date=end_date)
        if warning:
            raise HTTPException(status_code=404, detail=warning)
        if df.empty:
            raise HTTPException(status_code=404, detail="no data")

        prepared = add_return_features(df)
        prediction = ml_predictor.predict_next_close(
            prepared["Close"], horizon=max(1, int(horizon))
        )
        drift = ml_predictor.detect_factor_drift(prepared["Return"].fillna(0.0))
        return {
            "ticker": ticker,
            "prediction": prediction,
            "drift": drift,
        }

    @_route("post", "/governance/strategies/proposals")
    def governance_submit_proposal(payload: GovernanceProposalCreate):
        proposal_id = governance.submit_proposal(
            StrategyProposal(
                strategy_name=payload.strategy_name,
                created_by=payload.created_by,
                rationale=payload.rationale,
            )
        )
        return {"id": int(proposal_id), "status": "PENDING"}

    @_route("get", "/governance/strategies/proposals")
    def governance_list_proposals(status: str = "", limit: int = 200):
        frame = governance.list_proposals(status=status or None, limit=limit)
        return frame.to_dict(orient="records")

    @_route("post", "/governance/strategies/proposals/{proposal_id}/approve")
    def governance_approve_proposal(proposal_id: int, payload: GovernanceDecisionRequest):
        updated = governance.approve_proposal(proposal_id, approved_by=payload.approved_by)
        if not updated:
            raise HTTPException(status_code=404, detail="proposal not found or already decided")
        return {"id": int(proposal_id), "status": "APPROVED"}

    @_route("post", "/governance/strategies/proposals/{proposal_id}/reject")
    def governance_reject_proposal(proposal_id: int, payload: GovernanceDecisionRequest):
        updated = governance.reject_proposal(proposal_id, approved_by=payload.approved_by)
        if not updated:
            raise HTTPException(status_code=404, detail="proposal not found or already decided")
        return {"id": int(proposal_id), "status": "REJECTED"}

    @_route("post", "/integrations/webhooks/dispatch")
    def dispatch_webhook(payload: WebhookDispatchRequest):
        try:
            result = webhook_notifier.send(
                payload.url,
                WebhookPayload(
                    event=payload.event,
                    message=payload.message,
                    source=payload.source,
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result

    @_route("get", "/users/{username}/reports/portfolio")
    def portfolio_report(username: str, prices: str = "", session_id: str = ""):
        _require_authenticated_user(username, session_id)
        _authorize_module(username, "Reports")
        summary = portfolio.compute_portfolio_metrics(username, latest_prices=parse_prices(prices))
        positions = portfolio.list_positions(username)
        pdf = reports.build_portfolio_report(
            title=f"QuantVision Portfolio Report | {username}",
            portfolio_metrics=summary,
            positions=positions,
        )
        event_tracker.track(
            AnalyticsEvent(
                username=username,
                feature="reports",
                event_name="export_report",
                metadata="portfolio_report",
            )
        )
        return {
            "username": username,
            "summary": summary,
            "positions": positions.to_dict(orient="records"),
            "pdf_bytes": len(pdf),
        }

    return app
