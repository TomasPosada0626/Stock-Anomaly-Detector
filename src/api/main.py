from __future__ import annotations

from typing import Dict

from services.alerts_service import AlertsService
from services.auth_service import AuthService
from services.portfolio_service import PortfolioService

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


def create_app(
    auth_service: AuthService | None = None,
    portfolio_service: PortfolioService | None = None,
    alerts_service: AlertsService | None = None,
):
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Add fastapi and uvicorn to run the API layer.")

    auth = auth_service or AuthService()
    portfolio = portfolio_service or PortfolioService()
    alerts = alerts_service or AlertsService()

    app = FastAPI(title="QuantVision API", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "quantvision-api"}

    @app.get("/users/{username}/role")
    def user_role(username: str) -> dict[str, str]:
        return {"username": username, "role": auth.get_user_role(username)}

    @app.get("/users/{username}/portfolio/summary")
    def portfolio_summary(username: str, prices: str = "") -> dict[str, float]:
        price_map = parse_prices(prices)
        return portfolio.compute_portfolio_metrics(username, latest_prices=price_map)

    @app.get("/users/{username}/alerts/history")
    def alerts_history(username: str, limit: int = 100):
        if limit <= 0:
            raise HTTPException(status_code=400, detail="limit must be positive")
        frame = alerts.list_history(username, limit=limit)
        return frame.to_dict(orient="records")

    return app
