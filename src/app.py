import secrets
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from analytics.event_tracker import AnalyticsEvent, EventTracker
from analytics.experimentation import ExperimentationService
from config import SESSION_TTL_MINUTES, USERS_DB_PATH
from integrations.webhooks import WebhookNotifier, WebhookPayload
from security.input_validation import require_ticker_whitelist, sanitize_csv_upload, sanitize_ticker
from services.alerts_service import AlertRule, AlertsService
from services.auth_service import AuthService
from services.backtesting_service import BacktestingService
from services.indicators_service import add_indicators
from services.market_data_service import add_return_features, get_ticker_data
from services.ml_predictor_service import MLPredictorService
from services.observability import get_logger
from services.performance_service import (
    get_async_job_result,
    paginate_dataframe,
    submit_async_job,
)
from services.portfolio_service import PortfolioService, PositionInput
from services.reports_service import ReportsService
from services.risk_analytics_service import summarize_risk
from services.strategy_governance_service import StrategyGovernanceService, StrategyProposal
from services.watchlist_service import WatchlistInput, WatchlistService
from ui.auth_ui import render_login_panel
from ui.charts import (
    build_candlestick_chart,
    build_comparison_chart,
)
from ui.pages import render_anomalies_page, render_dashboard_page
from utils import rolling_quantile_anomaly

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
        token = secrets.token_urlsafe(24)
        st.session_state["csrf_token"] = token
    return str(token)


def _is_valid_csrf(token: str) -> bool:
    return bool(token) and token == st.session_state.get("csrf_token", "")


def _apply_theme() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background: radial-gradient(circle at 15% 20%, #0f2237 0%, #070b14 45%, #03050a 100%);
                color: #f5f8ff;
            }
            [data-testid="stMetricValue"] {
                color: #e7f0ff;
            }
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


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [col[0] if isinstance(col, tuple) else col for col in out.columns]
    if "Close" not in out.columns and len(out.columns) > 0:
        out["Close"] = pd.to_numeric(out.iloc[:, 0], errors="coerce")
    out["Open"] = pd.to_numeric(out.get("Open", out["Close"]), errors="coerce")
    out["High"] = pd.to_numeric(out.get("High", out["Close"]), errors="coerce")
    out["Low"] = pd.to_numeric(out.get("Low", out["Close"]), errors="coerce")
    out["Volume"] = pd.to_numeric(out.get("Volume", 0), errors="coerce").fillna(0)
    return out


def _load_market_data(
    tickers: list[str],
    start_date,
    end_date,
    uploaded_file,
) -> dict[str, pd.DataFrame]:
    results: dict[str, pd.DataFrame] = {}

    @st.cache_data(show_spinner=False, ttl=60 * 30)
    def _cached_prepare_ticker(ticker: str, start_str: str, end_str: str) -> pd.DataFrame:
        frame, _, warning_message = get_ticker_data(
            ticker=ticker,
            start_date=start_str,
            end_date=end_str,
            data_dir="data",
        )
        if warning_message or frame.empty:
            return pd.DataFrame()
        normalized = _normalize_ohlcv(frame)
        normalized = add_return_features(normalized)
        normalized = add_indicators(normalized)
        normalized["Anomaly_rolling_quantile_base"] = rolling_quantile_anomaly(
            normalized["Close"], window=20, quantile=0.95
        )
        return normalized

    if uploaded_file is not None:
        try:
            csv_text = uploaded_file.getvalue().decode("utf-8", errors="replace")
            custom_df = sanitize_csv_upload(csv_text)
            if "Date" in custom_df.columns:
                custom_df = custom_df.set_index("Date")
            custom_df.index = pd.to_datetime(custom_df.index)
            custom_df = _normalize_ohlcv(custom_df)
            custom_df = add_return_features(custom_df)
            custom_df = add_indicators(custom_df)
            custom_df["Anomaly_rolling_quantile_base"] = rolling_quantile_anomaly(
                custom_df["Close"], window=20, quantile=0.95
            )
            results["USER_CSV"] = custom_df
            event_tracker.track(
                AnalyticsEvent(
                    username=st.session_state.get("username", "anonymous"),
                    feature="market_data",
                    event_name="load_market_data",
                    metadata="source=csv",
                )
            )
        except Exception as csv_error:
            st.sidebar.error(f"CSV parse error: {csv_error}")

    for ticker in tickers:
        try:
            safe_ticker = sanitize_ticker(ticker)
            normalized = _cached_prepare_ticker(
                safe_ticker,
                str(start_date),
                str(end_date),
            )
            if normalized.empty:
                continue
            results[safe_ticker] = normalized
            event_tracker.track(
                AnalyticsEvent(
                    username=st.session_state.get("username", "anonymous"),
                    feature="market_data",
                    event_name="load_market_data",
                    metadata=f"source=ticker;ticker={safe_ticker}",
                )
            )
        except Exception as data_error:
            logger.exception("market_data_load_failed ticker=%s", ticker)
            st.error(f"Data load failed for {ticker}: {data_error}")

    return results


def _render_header(username: str, role: str) -> None:
    st.markdown('<div class="brand-title">QuantVision</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="brand-subtitle">Intelligent Financial Analytics Platform</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Authenticated as {username} | Role: {role}")


def _render_comparison(market_data: dict[str, pd.DataFrame]) -> None:
    st.subheader("Asset Comparison")
    if len(market_data) < 2:
        st.info("Select at least two assets to enable comparative analytics.")
        return

    compare_df = pd.DataFrame({ticker: df["Close"] for ticker, df in market_data.items()}).dropna()
    returns = compare_df.pct_change().dropna()
    cumulative = (1 + returns).cumprod() - 1
    drawdowns = compare_df / compare_df.cummax() - 1

    summary_rows = []
    for ticker in compare_df.columns:
        r = returns[ticker]
        summary_rows.append(
            {
                "Ticker": ticker,
                "Return %": float(cumulative[ticker].iloc[-1] * 100),
                "Volatility %": float(r.std(ddof=0) * np.sqrt(252) * 100),
                "Sharpe": float(
                    (r.mean() / r.std(ddof=0) * np.sqrt(252)) if r.std(ddof=0) > 0 else 0
                ),
                "Max Drawdown %": float(drawdowns[ticker].min() * 100),
            }
        )

    st.dataframe(pd.DataFrame(summary_rows), width="stretch")
    st.plotly_chart(
        build_comparison_chart(compare_df, "Multi-Asset Price Comparison"), width="stretch"
    )
    st.plotly_chart(
        build_comparison_chart(cumulative, "Cumulative Return Comparison"), width="stretch"
    )
    st.markdown("### Correlation Matrix")
    st.dataframe(returns.corr(), width="stretch")


def _render_portfolio(market_data: dict[str, pd.DataFrame], username: str) -> None:
    st.subheader("Portfolio Tracker")
    with st.form("portfolio_add_form"):
        security_token = st.text_input("Security Token", value=_csrf_token(), type="password")
        cols = st.columns(4)
        ticker = cols[0].text_input("Ticker", value="AAPL").upper().strip()
        quantity = cols[1].number_input("Quantity", min_value=0.0, value=10.0, step=1.0)
        buy_price = cols[2].number_input("Buy Price", min_value=0.0, value=100.0, step=0.5)
        buy_date = cols[3].date_input("Buy Date", value=datetime.today()).isoformat()
        submitted = st.form_submit_button("Add Position")
        if submitted and not _is_valid_csrf(security_token):
            st.error("Security token mismatch. Reload and try again.")
        elif submitted and ticker and quantity > 0 and buy_price > 0:
            portfolio_service.add_position(
                PositionInput(
                    username=username,
                    ticker=ticker,
                    quantity=float(quantity),
                    buy_price=float(buy_price),
                    buy_date=buy_date,
                )
            )
            st.success("Position saved.")

    positions = portfolio_service.list_positions(username)
    st.dataframe(positions, width="stretch")

    latest_prices: dict[str, float] = {}
    for ticker in positions.get("ticker", pd.Series(dtype=str)).unique().tolist():
        if ticker in market_data and not market_data[ticker].empty:
            latest_prices[ticker] = float(market_data[ticker]["Close"].iloc[-1])
    metrics = portfolio_service.compute_portfolio_metrics(username, latest_prices)

    cols = st.columns(4)
    cols[0].metric("Invested Capital", f"${metrics['Invested Capital']:,.2f}")
    cols[1].metric("Current Value", f"${metrics['Current Value']:,.2f}")
    cols[2].metric("PnL", f"${metrics['PnL']:,.2f}")
    cols[3].metric("ROI", f"{metrics['ROI %']:.2f}%")


def _render_watchlists(username: str) -> None:
    st.subheader("Watchlists")
    with st.form("watchlist_create_form"):
        security_token = st.text_input("Security Token", value=_csrf_token(), type="password")
        name = st.text_input("Watchlist name", value="Technology")
        create = st.form_submit_button("Create / Get")
        if create and not _is_valid_csrf(security_token):
            st.error("Security token mismatch. Reload and try again.")
        elif create and name.strip():
            watchlist_id = watchlist_service.create_watchlist(
                WatchlistInput(username=username, name=name)
            )
            st.session_state["active_watchlist_id"] = watchlist_id
            st.success(f"Watchlist ready: {name}")

    watchlists = paginate_dataframe(
        watchlist_service.list_watchlists(username), limit=50, sort_by="id", descending=True
    )
    st.dataframe(watchlists, width="stretch")
    if watchlists.empty:
        return

    selected_id = int(
        st.selectbox(
            "Active watchlist", options=watchlists["id"].tolist(), index=0, key="watchlist_id"
        )
    )
    items = watchlist_service.list_items(selected_id)
    st.write("Tickers", ", ".join(items["ticker"].tolist()) if not items.empty else "(empty)")

    col_a, col_b = st.columns(2)
    with col_a:
        ticker_to_add = st.text_input("Ticker to add", value="MSFT").upper().strip()
        if st.button("Add ticker") and ticker_to_add:
            watchlist_service.add_ticker(selected_id, ticker_to_add)
            st.rerun()
    with col_b:
        ticker_to_remove = st.text_input("Ticker to remove", value="").upper().strip()
        if st.button("Remove ticker") and ticker_to_remove:
            watchlist_service.remove_ticker(selected_id, ticker_to_remove)
            st.rerun()


def _evaluate_alert_conditions(
    df: pd.DataFrame, rule_type: str, threshold: float | None
) -> tuple[bool, str]:
    if len(df) < 3:
        return False, "insufficient data"

    current = df.iloc[-1]
    previous = df.iloc[-2]

    if rule_type == "anomaly_detected":
        triggered = bool(current.get("Anomaly_rolling_quantile_base", False))
        return triggered, "Rolling quantile anomaly detected"
    if rule_type == "rsi_gt_70":
        triggered = float(current.get("RSI_14", 0)) > 70
        return triggered, f"RSI at {current.get('RSI_14', 0):.2f}"
    if rule_type == "rsi_lt_30":
        triggered = float(current.get("RSI_14", 100)) < 30
        return triggered, f"RSI at {current.get('RSI_14', 0):.2f}"
    if rule_type == "macd_crossover":
        triggered = float(previous.get("MACD", 0)) <= float(
            previous.get("MACD_Signal", 0)
        ) and float(current.get("MACD", 0)) > float(current.get("MACD_Signal", 0))
        return triggered, "MACD bullish crossover"
    if rule_type == "ema_crossover":
        triggered = float(previous.get("EMA_20", 0)) <= float(previous.get("SMA_20", 0)) and float(
            current.get("EMA_20", 0)
        ) > float(current.get("SMA_20", 0))
        return triggered, "EMA crossed above SMA"
    if rule_type == "price_change_pct":
        target = float(threshold if threshold is not None else 5)
        change = ((float(current["Close"]) / float(previous["Close"])) - 1) * 100
        triggered = abs(change) >= target
        return triggered, f"Price changed {change:.2f}%"
    if rule_type == "new_high":
        triggered = float(current["Close"]) >= float(df["Close"].tail(252).max())
        return triggered, "New 52-week high"
    if rule_type == "new_low":
        triggered = float(current["Close"]) <= float(df["Close"].tail(252).min())
        return triggered, "New 52-week low"
    return False, "rule not supported"


def _render_alerts(market_data: dict[str, pd.DataFrame], username: str) -> None:
    st.subheader("Smart Alerts")
    rule_types = [
        "anomaly_detected",
        "rsi_gt_70",
        "rsi_lt_30",
        "macd_crossover",
        "ema_crossover",
        "price_change_pct",
        "new_high",
        "new_low",
    ]
    with st.form("alert_rule_form"):
        security_token = st.text_input("Security Token", value=_csrf_token(), type="password")
        cols = st.columns(3)
        ticker = cols[0].text_input("Ticker", value="AAPL").upper().strip()
        rule_type = cols[1].selectbox("Rule Type", options=rule_types)
        threshold = cols[2].number_input("Threshold (optional)", value=5.0)
        create_rule = st.form_submit_button("Create Rule")
        if create_rule and not _is_valid_csrf(security_token):
            st.error("Security token mismatch. Reload and try again.")
        elif create_rule and ticker:
            threshold_value = threshold if rule_type == "price_change_pct" else None
            alerts_service.create_rule(
                AlertRule(
                    username=username,
                    ticker=ticker,
                    alert_type=rule_type,
                    threshold=threshold_value,
                    active=True,
                )
            )
            st.success("Rule created.")

    rules = alerts_service.list_rules(username)
    st.dataframe(rules, width="stretch")

    if st.button("Evaluate Active Rules"):
        for _, row in rules[rules["active"] == 1].iterrows():
            ticker = str(row["ticker"]).upper()
            if ticker not in market_data:
                continue
            triggered, message = _evaluate_alert_conditions(
                market_data[ticker], str(row["alert_type"]), row.get("threshold")
            )
            if triggered:
                alerts_service.emit_alert(username, ticker, str(row["alert_type"]), message)
        st.success("Rule evaluation completed.")

    st.markdown("### Alert History")
    history = paginate_dataframe(
        alerts_service.list_history(username), limit=50, sort_by="triggered_at", descending=True
    )
    st.dataframe(history, width="stretch")


def _render_backtesting(market_data: dict[str, pd.DataFrame]) -> None:
    st.subheader("Backtesting Engine")
    if not market_data:
        st.info("Load market data first.")
        return
    ticker = st.selectbox("Ticker", options=list(market_data.keys()), key="backtest_ticker")
    df = market_data[ticker].copy()
    if df.empty:
        return

    # Example strategy: buy on RSI < 30 and anomaly, sell on RSI > 70 or MACD bearish crossover.
    df["buy_signal"] = (df["RSI_14"] < 30) | (df["Anomaly_rolling_quantile_base"])
    df["sell_signal"] = (df["RSI_14"] > 70) | (
        (df["MACD"].shift(1) >= df["MACD_Signal"].shift(1)) & (df["MACD"] < df["MACD_Signal"])
    )
    results = backtesting_service.run_simple_strategy(df, "buy_signal", "sell_signal")

    cols = st.columns(5)
    cols[0].metric("Return", f"{results['Return %']:.2f}%")
    cols[1].metric("Trades", f"{int(results['Trades'])}")
    cols[2].metric("Win Rate", f"{results['Win Rate %']:.2f}%")
    cols[3].metric("Buy & Hold", f"{results['Buy & Hold %']:.2f}%")
    cols[4].metric("Max Drawdown", f"{results['Max Drawdown %']:.2f}%")


def _render_ai_lab(market_data: dict[str, pd.DataFrame]) -> None:
    st.subheader("AI Lab")
    if not market_data:
        st.info("Load market data first.")
        return

    ticker = st.selectbox("AI ticker", options=list(market_data.keys()), key="ai_ticker")
    horizon = st.slider("Prediction horizon (days)", min_value=1, max_value=30, value=5)
    frame = market_data[ticker]

    prediction = ml_predictor_service.predict_next_close(frame["Close"], horizon=horizon)
    drift = ml_predictor_service.detect_factor_drift(frame["Return"].fillna(0.0))

    cols = st.columns(3)
    cols[0].metric("Current Close", f"${prediction['current_close']:.2f}")
    cols[1].metric("Predicted Close", f"${prediction['predicted_close']:.2f}")
    cols[2].metric("Expected Change", f"{prediction['expected_change_pct']:.2f}%")

    st.write("Drift", drift)
    event_tracker.track(
        AnalyticsEvent(
            username=st.session_state.get("username", "anonymous"),
            feature="ai_lab",
            event_name="run_ml_prediction",
            metadata=f"ticker={ticker};horizon={horizon}",
        )
    )


def _render_governance() -> None:
    st.subheader("Strategy Governance")
    with st.form("governance_form"):
        security_token = st.text_input("Security Token", value=_csrf_token(), type="password")
        strategy_name = st.text_input("Strategy name", value="Momentum Plus")
        rationale = st.text_area(
            "Rationale", value="Add anomaly filters to reduce false positives."
        )
        submitted = st.form_submit_button("Submit proposal")
        if submitted and not _is_valid_csrf(security_token):
            st.error("Security token mismatch. Reload and try again.")
        elif submitted:
            proposal_id = governance_service.submit_proposal(
                StrategyProposal(
                    strategy_name=strategy_name,
                    created_by=st.session_state.get("username", "unknown"),
                    rationale=rationale,
                )
            )
            st.success(f"Proposal submitted: {proposal_id}")

    proposals = governance_service.list_proposals(limit=200)
    st.dataframe(proposals, width="stretch")

    if proposals.empty:
        return
    proposal_id = int(st.selectbox("Proposal ID", options=proposals["id"].tolist(), key="gov_id"))
    col_a, col_b = st.columns(2)
    if col_a.button("Approve"):
        governance_service.approve_proposal(
            proposal_id, approved_by=st.session_state.get("username", "admin")
        )
        st.rerun()
    if col_b.button("Reject"):
        governance_service.reject_proposal(
            proposal_id, approved_by=st.session_state.get("username", "admin")
        )
        st.rerun()

    st.markdown("### Webhook Dispatch")
    webhook_url = st.text_input("Webhook URL", value="https://example.com/hook")
    webhook_message = st.text_input("Webhook message", value="Strategy governance update")
    if st.button("Send Webhook Notification"):
        try:
            result = webhook_notifier.send(
                webhook_url,
                WebhookPayload(
                    event="governance_update",
                    message=webhook_message,
                    source="quantvision_ui",
                ),
            )
            st.success(f"Webhook dispatched (status={result['status']})")
        except Exception as exc:
            st.error(f"Webhook failed: {exc}")


def _render_analytics_dashboard() -> None:
    st.subheader("Usage Analytics")
    events = event_tracker.list_events(limit=500)
    st.dataframe(events, width="stretch")

    top = event_tracker.top_features(limit=10)
    st.markdown("### Top Features")
    st.dataframe(top, width="stretch")

    funnel = event_tracker.funnel()
    st.markdown("### Funnel")
    st.json(funnel)

    st.markdown("### A/B Experimentation")
    with st.form("ab_create_form"):
        exp_name = st.text_input("Experiment name", value="dashboard_cta_v1")
        exp_feature = st.text_input("Feature", value="dashboard")
        exp_variants = st.text_input("Variants (comma separated)", value="control,treatment")
        exp_hypothesis = st.text_area("Hypothesis", value="Treatment increases click-through rate")
        create_exp = st.form_submit_button("Create / Update Experiment")
        if create_exp:
            variants = [item.strip() for item in exp_variants.split(",") if item.strip()]
            experimentation_service.create_experiment(
                name=exp_name,
                feature=exp_feature,
                variants=variants,
                hypothesis=exp_hypothesis,
            )
            st.success(f"Experiment ready: {exp_name}")

    experiments = experimentation_service.list_experiments()
    st.dataframe(experiments, width="stretch")
    if experiments.empty:
        return

    selected_experiment = st.selectbox("Experiment", options=experiments["name"].tolist())
    username = st.text_input(
        "Username for assignment/conversion",
        value=st.session_state.get("username", "guest"),
    )
    col_a, col_b = st.columns(2)
    if col_a.button("Assign Variant"):
        variant = experimentation_service.assign_variant(selected_experiment, username)
        event_tracker.track(
            AnalyticsEvent(
                username=username,
                feature="experimentation",
                event_name="ab_exposure",
                metadata=f"experiment={selected_experiment};variant={variant}",
            )
        )
        st.info(f"Assigned variant: {variant}")
    if col_b.button("Mark Conversion"):
        experimentation_service.track_conversion(selected_experiment, username)
        event_tracker.track(
            AnalyticsEvent(
                username=username,
                feature="experimentation",
                event_name="ab_conversion",
                metadata=f"experiment={selected_experiment}",
            )
        )
        st.success("Conversion marked")

    st.markdown("### Experiment Summary")
    st.dataframe(experimentation_service.summary(selected_experiment), width="stretch")


def _render_risk(market_data: dict[str, pd.DataFrame], focus_ticker: str) -> None:
    st.subheader("Risk Analytics")
    if focus_ticker not in market_data:
        st.info("Load market data first.")
        return

    asset_df = market_data[focus_ticker]
    benchmark_options = [ticker for ticker in market_data.keys() if ticker != focus_ticker]
    benchmark_name = (
        st.selectbox("Benchmark", options=benchmark_options, index=0) if benchmark_options else ""
    )
    benchmark_returns = (
        market_data[benchmark_name]["Return"]
        if benchmark_name and benchmark_name in market_data
        else None
    )
    risk = summarize_risk(asset_df["Return"], benchmark_returns=benchmark_returns)
    st.dataframe(pd.DataFrame([risk]), width="stretch")


def _render_reports(market_data: dict[str, pd.DataFrame], username: str) -> None:
    st.subheader("Reports Center")
    if not market_data:
        st.info("Load market data first to generate reports.")
        return

    ticker = st.selectbox("Report ticker", options=list(market_data.keys()), key="report_ticker")
    df = market_data[ticker]
    if df.empty:
        st.warning("Selected ticker has no data.")
        return

    risk_summary = summarize_risk(df["Return"])
    kpis = {
        "Current Price": float(df["Close"].iloc[-1]),
        "Average Volume": float(df["Volume"].tail(20).mean()),
        "Return 1Y %": (
            float(((df["Close"].iloc[-1] / df["Close"].tail(252).iloc[0]) - 1) * 100)
            if len(df) >= 252
            else float(((df["Close"].iloc[-1] / df["Close"].iloc[0]) - 1) * 100)
        ),
        "Volatility": float(risk_summary["Volatility"]),
        "Sharpe": float(risk_summary["Sharpe Ratio"]),
    }
    benchmark = pd.DataFrame([risk_summary])

    pdf_bytes = reports_service.build_executive_report(
        title=f"QuantVision Executive Report | {ticker} | {username}",
        kpis=kpis,
        benchmark=benchmark,
    )
    csv_bytes = reports_service.to_csv_bytes(df.tail(500))
    png_bytes = reports_service.to_png_bytes(build_candlestick_chart(df, ticker))

    st.dataframe(pd.DataFrame([kpis]), width="stretch")
    if st.button("Generate PDF Asynchronously"):
        job_id = f"report_{username}_{ticker}_{int(datetime.now().timestamp())}"
        submit_async_job(
            job_id,
            reports_service.build_executive_report,
            f"QuantVision Executive Report | {ticker} | {username}",
            kpis,
            benchmark,
        )
        st.session_state["report_job_id"] = job_id
        st.info(f"Report job queued: {job_id}")

    active_job_id = st.session_state.get("report_job_id", "")
    if active_job_id:
        status, payload = get_async_job_result(active_job_id)
        st.caption(f"Async report job status: {status}")
        if status == "completed" and isinstance(payload, (bytes, bytearray)):
            st.download_button(
                "Download Async Executive Report (PDF)",
                data=payload,
                file_name=f"{ticker}_executive_report_async.pdf",
                mime="application/pdf",
            )
    st.download_button(
        "Download Executive Report (PDF)",
        data=pdf_bytes,
        file_name=f"{ticker}_executive_report.pdf",
        mime="application/pdf",
    )
    st.download_button(
        "Download Technical Dataset (CSV)",
        data=csv_bytes,
        file_name=f"{ticker}_technical_report.csv",
        mime="text/csv",
    )
    if png_bytes:
        st.download_button(
            "Download Chart Snapshot (PNG)",
            data=png_bytes,
            file_name=f"{ticker}_chart_snapshot.png",
            mime="image/png",
        )


def _render_admin() -> None:
    st.subheader("Administration")
    users = auth_service.list_users()
    if not users:
        st.info("No users found in local auth database.")
        return

    users_df = pd.DataFrame(users, columns=["username", "email", "role"])
    st.dataframe(users_df, width="stretch")

    selected_username = st.selectbox("User", options=users_df["username"].tolist())
    selected_role = st.selectbox("Role", options=["ADMIN", "ANALYST", "GUEST"])
    if st.button("Update Role"):
        updated = auth_service.set_user_role(selected_username, selected_role)
        if updated:
            st.success(f"Role updated: {selected_username} -> {selected_role}")
            if st.session_state.get("username") == selected_username:
                st.session_state["role"] = selected_role
        else:
            st.error("Role update failed.")


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

if st.session_state.get("logged_in"):
    if st.sidebar.button("Logout"):
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
allowed_modules = auth_service.modules_for_role(role)
module = st.sidebar.radio(
    "Workspace",
    options=allowed_modules,
)

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

default_start = datetime(datetime.today().year - 2, 1, 1)
start_date = st.sidebar.date_input("Start Date", value=default_start)
end_date = st.sidebar.date_input("End Date", value=datetime.today())

method_options = [
    "Z-Score",
    "I-Forest",
    "DBSCAN",
    "Prophet",
    "Rolling Quantile",
    "LOF",
    "One-Class SVM",
]
selected_methods = st.sidebar.multiselect(
    "Anomaly methods",
    options=method_options,
    default=["Z-Score", "I-Forest", "LOF"],
)

params = {
    "zscore_threshold": st.sidebar.slider("Z-Score threshold", 1.0, 5.0, 3.0, 0.1),
    "iforest_contamination": st.sidebar.slider("Contamination", 0.001, 0.2, 0.01, 0.001),
    "dbscan_eps": st.sidebar.slider("DBSCAN eps", 0.01, 0.4, 0.08, 0.01),
    "dbscan_min_samples": st.sidebar.slider("DBSCAN min_samples", 2, 30, 6, 1),
    "rolling_window": st.sidebar.slider("Rolling window", 5, 90, 20, 1),
    "quantile_low": st.sidebar.slider("Low quantile", 0.01, 0.2, 0.05, 0.01),
    "quantile_high": st.sidebar.slider("High quantile", 0.8, 0.99, 0.95, 0.01),
    "lof_neighbors": st.sidebar.slider("LOF neighbors", 5, 60, 20, 1),
    "ocsvm_nu": st.sidebar.slider("One-Class SVM nu", 0.01, 0.4, 0.05, 0.01),
}

if st.sidebar.button("Load / Refresh Market Data"):
    st.session_state["market_data"] = _load_market_data(
        tickers, start_date, end_date, uploaded_file
    )

market_data = st.session_state.get("market_data", {})
focus_ticker = st.sidebar.selectbox(
    "Focus ticker",
    options=list(market_data.keys()) if market_data else ["AAPL"],
)

if module == "Dashboard":
    render_dashboard_page(market_data, focus_ticker)
elif module == "Anomalies":
    render_anomalies_page(market_data, selected_methods, params)
elif module == "Comparison":
    _render_comparison(market_data)
elif module == "Portfolio":
    _render_portfolio(market_data, username)
elif module == "Watchlists":
    _render_watchlists(username)
elif module == "Alerts":
    _render_alerts(market_data, username)
elif module == "Backtesting":
    _render_backtesting(market_data)
elif module == "Risk":
    _render_risk(market_data, focus_ticker)
elif module == "Reports":
    _render_reports(market_data, username)
elif module == "AI Lab":
    _render_ai_lab(market_data)
elif module == "Governance":
    _render_governance()
elif module == "Analytics":
    _render_analytics_dashboard()
elif module == "Admin":
    _render_admin()
