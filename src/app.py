# ruff: noqa: E402
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

SRC_DIR = str(Path(__file__).resolve().parent)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from analytics.event_tracker import EventTracker
from analytics.experimentation import ExperimentationService
from config import SESSION_TTL_MINUTES, USERS_DB_PATH
from integrations.webhooks import WebhookNotifier
from security.csrf import generate_csrf_token, verify_csrf_token
from security.input_validation import require_ticker_whitelist
from services.alerts_service import AlertsService
from services.auth_service import AuthService
from services.backtesting_service import BacktestingService
from services.ml_predictor_service import MLPredictorService
from services.observability import get_logger
from services.portfolio_service import PortfolioService
from services.reports_service import ReportsService
from services.strategy_governance_service import StrategyGovernanceService
from services.watchlist_service import WatchlistService
from ui.auth_ui import render_login_panel
from ui.data_loader import load_market_data, load_ticker_lazy
from ui.pages import (
    render_admin_page,
    render_ai_lab_page,
    render_alerts_page,
    render_analytics_dashboard_page,
    render_anomalies_page,
    render_backtesting_page,
    render_comparison_page,
    render_dashboard_page,
    render_governance_page,
    render_portfolio_page,
    render_reports_page,
    render_risk_page,
    render_watchlists_page,
)

st.set_page_config(page_title="QuantVision", layout="wide")

logger = get_logger("app")
auth_service = AuthService(db_path=USERS_DB_PATH)
portfolio_service = PortfolioService()
watchlist_service = WatchlistService()
alerts_service = AlertsService()
backtesting_service = BacktestingService()
reports_service = ReportsService()
event_tracker = EventTracker()
experimentation_service = ExperimentationService()
governance_service = StrategyGovernanceService()
ml_predictor_service = MLPredictorService()
webhook_notifier = WebhookNotifier()
auth_service.initialize()
logger.info("quantvision_initialized")


def _csrf_token() -> str:
    token = st.session_state.get("csrf_token", "")
    if not token:
        token = generate_csrf_token()
        st.session_state["csrf_token"] = token
    return str(token)


def _is_valid_csrf(token: str) -> bool:
    return bool(verify_csrf_token(token, st.session_state))


def _apply_theme() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background: radial-gradient(circle at 15% 20%, #0f2237 0%, #070b14 45%, #03050a 100%);
                color: #f5f8ff;
            }
            [data-testid="stMetricValue"] { color: #e7f0ff; }
            div[data-testid="stSidebar"] {
                background: linear-gradient(180deg, #0e1f32 0%, #08111f 100%);
            }
            .brand-title {
                font-size: 2.1rem;
                font-weight: 700;
                letter-spacing: 0.04rem;
                color: #9cc7ff;
            }
            .brand-subtitle {
                color: #cddfff;
                margin-top: -0.3rem;
                margin-bottom: 1.0rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header(username: str, role: str) -> None:
    st.markdown('<div class="brand-title">QuantVision</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="brand-subtitle">Intelligent Financial Analytics Platform</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Authenticated as {username} | Role: {role}")


_apply_theme()

if st.session_state.get("logged_in"):
    current_session_id = st.session_state.get("session_id", "")
    if not current_session_id or not auth_service.is_session_valid(current_session_id):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.session_state["session_id"] = ""
        st.warning(
            f"Your session has expired after {SESSION_TTL_MINUTES} minutes. Please log in again."
        )
        st.rerun()

if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    render_login_panel(auth_service)
    st.stop()

if st.session_state.get("logged_in") and st.sidebar.button("Logout"):
    current_session_id = st.session_state.get("session_id", "")
    if current_session_id:
        auth_service.invalidate_session(current_session_id)
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["session_id"] = ""
    st.success("You have been logged out.")
    st.rerun()

username = st.session_state.get("username", "")
if "role" not in st.session_state and username:
    st.session_state["role"] = auth_service.get_user_role(username)
role = str(st.session_state.get("role", "ANALYST")).upper()
_render_header(username, role)

st.sidebar.markdown("## QuantVision")
st.sidebar.caption("Intelligent Financial Analytics Platform")
st.sidebar.caption(f"Role: {role}")
module = st.sidebar.radio("Workspace", options=auth_service.modules_for_role(role))

uploaded_file = st.sidebar.file_uploader("Upload CSV market data", type=["csv"])
popular_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "JPM", "V", "DIS"]
tickers = st.sidebar.multiselect("Tickers", options=popular_tickers, default=["AAPL", "MSFT"])
custom_ticker = st.sidebar.text_input("Custom tickers (comma separated)", value="")
if custom_ticker.strip():
    for token in custom_ticker.split(","):
        candidate = token.strip().upper()
        if not candidate:
            continue
        try:
            tickers.append(require_ticker_whitelist(candidate, set(popular_tickers)))
        except ValueError:
            st.sidebar.warning(f"Ignored unsupported ticker: {candidate}")

tickers = sorted(set(tickers))
start_date = st.sidebar.date_input("Start Date", value=datetime(datetime.today().year - 2, 1, 1))
end_date = st.sidebar.date_input("End Date", value=datetime.today())

selected_methods = st.sidebar.multiselect(
    "Anomaly methods",
    options=[
        "Z-Score",
        "I-Forest",
        "DBSCAN",
        "Prophet",
        "Rolling Quantile",
        "LOF",
        "One-Class SVM",
    ],
    default=["Z-Score", "I-Forest", "LOF"],
)
params: dict[str, float] = {
    "zscore_threshold": st.sidebar.slider("Z-Score threshold", 1.0, 5.0, 3.0, 0.1),
    "iforest_contamination": st.sidebar.slider("Contamination", 0.001, 0.2, 0.01, 0.001),
    "dbscan_eps": st.sidebar.slider("DBSCAN eps", 0.01, 0.4, 0.08, 0.01),
    "dbscan_min_samples": float(st.sidebar.slider("DBSCAN min_samples", 2, 30, 6, 1)),
    "rolling_window": float(st.sidebar.slider("Rolling window", 5, 90, 20, 1)),
    "quantile_low": st.sidebar.slider("Low quantile", 0.01, 0.2, 0.05, 0.01),
    "quantile_high": st.sidebar.slider("High quantile", 0.8, 0.99, 0.95, 0.01),
    "lof_neighbors": float(st.sidebar.slider("LOF neighbors", 5, 60, 20, 1)),
    "ocsvm_nu": st.sidebar.slider("One-Class SVM nu", 0.01, 0.4, 0.05, 0.01),
}

if st.sidebar.button("Load / Refresh Market Data"):
    st.session_state["market_data"] = load_market_data(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        uploaded_file=uploaded_file,
        event_tracker=event_tracker,
        username=username or "anonymous",
    )

market_data = st.session_state.get("market_data", {})
if market_data and st.sidebar.button("Load Focus Ticker (lazy)"):
    st.session_state["market_data"] = {
        **market_data,
        "AAPL_LAZY": load_ticker_lazy("AAPL", years=5),
    }
    market_data = st.session_state.get("market_data", {})

focus_ticker = st.sidebar.selectbox(
    "Focus ticker", options=list(market_data.keys()) if market_data else ["AAPL"]
)
csrf_token_value = _csrf_token()

if module == "Dashboard":
    render_dashboard_page(market_data, focus_ticker)
elif module == "Anomalies":
    render_anomalies_page(market_data, selected_methods, params)
elif module == "Comparison":
    render_comparison_page(market_data)
elif module == "Portfolio":
    render_portfolio_page(
        market_data, username, portfolio_service, csrf_token_value, _is_valid_csrf
    )
elif module == "Watchlists":
    render_watchlists_page(username, watchlist_service, csrf_token_value, _is_valid_csrf)
elif module == "Alerts":
    render_alerts_page(market_data, username, alerts_service, csrf_token_value, _is_valid_csrf)
elif module == "Backtesting":
    render_backtesting_page(market_data, backtesting_service)
elif module == "Risk":
    render_risk_page(market_data, focus_ticker)
elif module == "Reports":
    render_reports_page(market_data, username, reports_service)
elif module == "AI Lab":
    render_ai_lab_page(market_data, ml_predictor_service, event_tracker, username)
elif module == "Governance":
    render_governance_page(
        governance_service,
        webhook_notifier,
        username,
        csrf_token_value,
        _is_valid_csrf,
    )
elif module == "Analytics":
    render_analytics_dashboard_page(event_tracker, experimentation_service, username)
elif module == "Admin":
    render_admin_page(auth_service)
