import time
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
from prophet import Prophet
from sklearn.cluster import DBSCAN

from anomaly_methods import (
    detect_anomalies_iforest,
    detect_anomalies_lof,
    detect_anomalies_one_class_svm,
    detect_anomalies_zscore,
)
from config import SESSION_TTL_MINUTES, USERS_DB_PATH
from services.alerts_service import AlertRule, AlertsService
from services.auth_service import AuthService
from services.backtesting_service import BacktestingService
from services.indicators_service import add_indicators
from services.market_data_service import add_return_features, get_ticker_data
from services.observability import get_logger
from services.portfolio_service import PortfolioService, PositionInput
from services.reports_service import ReportsService
from services.risk_analytics_service import summarize_risk
from services.watchlist_service import WatchlistInput, WatchlistService
from ui.auth_ui import render_login_panel
from ui.charts import (
    build_anomaly_chart,
    build_candlestick_chart,
    build_comparison_chart,
    build_price_chart,
    build_volume_chart,
)
from utils import rolling_quantile_anomaly

st.set_page_config(page_title="QuantVision", layout="wide")

logger = get_logger("app")
auth_service = AuthService(db_path=USERS_DB_PATH)
portfolio_service = PortfolioService()
watchlist_service = WatchlistService()
alerts_service = AlertsService()
backtesting_service = BacktestingService()
reports_service = ReportsService()
auth_service.initialize()
logger.info("quantvision_initialized")


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


def _run_anomaly_methods(
    df: pd.DataFrame,
    selected_methods: list[str],
    zscore_threshold: float,
    iforest_contamination: float,
    dbscan_eps: float,
    dbscan_min_samples: int,
    rolling_window: int,
    quantile_low: float,
    quantile_high: float,
    lof_neighbors: int,
    ocsvm_nu: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    model_df = df.copy()
    comparisons: list[dict[str, float | str]] = []
    method_labels: list[tuple[str, str]] = []

    for method in selected_methods:
        start = time.time()
        col_name = ""
        params: dict[str, float | int | str] = {}

        if method == "Z-Score":
            col_name = "Anomaly_zscore"
            model_df[col_name] = detect_anomalies_zscore(model_df["Return"], threshold=zscore_threshold)
            params = {"threshold": zscore_threshold}
        elif method == "I-Forest":
            col_name = "Anomaly_iforest"
            model_df[col_name] = detect_anomalies_iforest(
                model_df["Return"], contamination=iforest_contamination, random_state=42
            )
            params = {"contamination": iforest_contamination}
        elif method == "DBSCAN":
            col_name = "Anomaly_dbscan"
            mask = model_df["Return"].notna()
            model_df[col_name] = False
            values = model_df.loc[mask, ["Return"]].values.reshape(-1, 1)
            if len(values) > 0:
                db = DBSCAN(eps=dbscan_eps, min_samples=dbscan_min_samples)
                model_df.loc[mask, col_name] = db.fit_predict(values) == -1
            params = {"eps": dbscan_eps, "min_samples": dbscan_min_samples}
        elif method == "Prophet":
            col_name = "Anomaly_prophet"
            model_df[col_name] = False
            try:
                prophet_df = model_df[["Close"]].reset_index()
                prophet_df.columns = ["ds", "y"]
                prophet_df["ds"] = pd.to_datetime(prophet_df["ds"]).dt.tz_localize(None)
                model = Prophet(daily_seasonality=True)
                model.fit(prophet_df)
                forecast = model.predict(model.make_future_dataframe(periods=0))
                residuals = model_df["Close"].values - forecast["yhat"].values
                model_df[col_name] = np.abs(residuals) > 3 * np.std(residuals)
            except Exception as prophet_error:
                logger.warning("prophet_failed error=%s", str(prophet_error))
            params = {"residual_threshold": 3.0}
        elif method == "Rolling Quantile":
            col_name = "Anomaly_rolling_quantile"
            lower = model_df["Close"].rolling(window=rolling_window, min_periods=1).quantile(quantile_low)
            upper = model_df["Close"].rolling(window=rolling_window, min_periods=1).quantile(quantile_high)
            model_df[col_name] = (model_df["Close"] < lower) | (model_df["Close"] > upper)
            params = {"window": rolling_window, "q_low": quantile_low, "q_high": quantile_high}
        elif method == "LOF":
            col_name = "Anomaly_lof"
            model_df[col_name] = detect_anomalies_lof(
                model_df["Return"], contamination=iforest_contamination, n_neighbors=lof_neighbors
            )
            params = {"contamination": iforest_contamination, "n_neighbors": lof_neighbors}
        elif method == "One-Class SVM":
            col_name = "Anomaly_ocsvm"
            model_df[col_name] = detect_anomalies_one_class_svm(model_df["Return"], nu=ocsvm_nu)
            params = {"nu": ocsvm_nu}

        elapsed = time.time() - start
        if col_name:
            method_labels.append((col_name, method))
            comparisons.append(
                {
                    "Method": method,
                    "Anomalies": int(model_df[col_name].sum()),
                    "Time (s)": round(elapsed, 4),
                    "Parameters": str(params),
                }
            )

    anomaly_df = model_df.copy()
    anomaly_df["Method"] = "None"
    for col, label in method_labels:
        anomaly_df.loc[anomaly_df[col], "Method"] = label
    points = anomaly_df[anomaly_df["Method"] != "None"]
    return model_df, points, pd.DataFrame(comparisons)


def _load_market_data(
    tickers: list[str],
    start_date,
    end_date,
    uploaded_file,
) -> dict[str, pd.DataFrame]:
    results: dict[str, pd.DataFrame] = {}
    if uploaded_file is not None:
        try:
            custom_df = pd.read_csv(uploaded_file, parse_dates=True)
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
        except Exception as csv_error:
            st.sidebar.error(f"CSV parse error: {csv_error}")

    for ticker in tickers:
        try:
            df, downloaded, warning_message = get_ticker_data(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                data_dir="data",
            )
            if warning_message:
                st.warning(warning_message)
            if downloaded and not df.empty:
                st.toast(f"{ticker} updated from market source.")
            if df.empty:
                continue
            normalized = _normalize_ohlcv(df)
            normalized = add_return_features(normalized)
            normalized = add_indicators(normalized)
            normalized["Anomaly_rolling_quantile_base"] = rolling_quantile_anomaly(
                normalized["Close"], window=20, quantile=0.95
            )
            results[ticker] = normalized
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


def _render_dashboard(market_data: dict[str, pd.DataFrame], focus_ticker: str) -> None:
    st.subheader("Professional Market Dashboard")
    if focus_ticker not in market_data:
        st.info("Load market data from the sidebar to render dashboard metrics.")
        return

    df = market_data[focus_ticker].dropna(subset=["Close"]).copy()
    if df.empty:
        st.warning("No close price data available for this ticker.")
        return

    current_price = float(df["Close"].iloc[-1])
    previous_price = float(df["Close"].iloc[-2]) if len(df) > 1 else current_price
    daily_change_pct = ((current_price / previous_price) - 1) * 100 if previous_price else 0.0
    market_cap_proxy = current_price * float(df["Volume"].tail(20).mean())
    pe_proxy = max(0.0, current_price / max(0.5, float(df["Close"].tail(252).mean()) * 0.08))
    dividend_yield_proxy = max(0.0, min(8.0, float(df["Close"].pct_change().rolling(252).mean().iloc[-1] * 100)))
    beta_proxy = 1.0 + float(df["Return"].rolling(63).std().fillna(0).iloc[-1]) * 5
    high_52 = float(df["Close"].tail(252).max())
    low_52 = float(df["Close"].tail(252).min())

    row1 = st.columns(4)
    row1[0].metric("Price", f"${current_price:,.2f}", f"{daily_change_pct:.2f}%")
    row1[1].metric("Volume", f"{int(df['Volume'].iloc[-1]):,}")
    row1[2].metric("Market Cap (proxy)", f"${market_cap_proxy:,.0f}")
    row1[3].metric("P/E Ratio (proxy)", f"{pe_proxy:.2f}")

    row2 = st.columns(4)
    row2[0].metric("Dividend Yield (proxy)", f"{dividend_yield_proxy:.2f}%")
    row2[1].metric("Beta (proxy)", f"{beta_proxy:.2f}")
    row2[2].metric("52W High", f"${high_52:,.2f}")
    row2[3].metric("52W Low", f"${low_52:,.2f}")

    st.plotly_chart(build_candlestick_chart(df, focus_ticker), width="stretch")
    st.plotly_chart(build_volume_chart(df, focus_ticker), width="stretch")


def _render_anomalies(
    market_data: dict[str, pd.DataFrame],
    selected_methods: list[str],
    params: dict[str, float | int],
) -> None:
    st.subheader("Machine Learning Anomaly Detection Lab")
    if not market_data:
        st.info("Load market data from the sidebar to run anomaly detection.")
        return

    tabs = st.tabs(list(market_data.keys()))
    for idx, (ticker, raw_df) in enumerate(market_data.items()):
        with tabs[idx]:
            df = raw_df.copy()
            modeled, points, benchmark = _run_anomaly_methods(
                df=df,
                selected_methods=selected_methods,
                zscore_threshold=float(params["zscore_threshold"]),
                iforest_contamination=float(params["iforest_contamination"]),
                dbscan_eps=float(params["dbscan_eps"]),
                dbscan_min_samples=int(params["dbscan_min_samples"]),
                rolling_window=int(params["rolling_window"]),
                quantile_low=float(params["quantile_low"]),
                quantile_high=float(params["quantile_high"]),
                lof_neighbors=int(params["lof_neighbors"]),
                ocsvm_nu=float(params["ocsvm_nu"]),
            )
            fig_price, y_data = build_price_chart(modeled, ticker)
            st.plotly_chart(fig_price, width="stretch")

            fig_anomaly = build_anomaly_chart(modeled, points, y_data)
            st.plotly_chart(fig_anomaly, width="stretch")

            st.markdown("### Benchmark")
            st.dataframe(benchmark, width="stretch")
            st.download_button(
                f"Export {ticker} anomalies CSV",
                modeled.to_csv().encode("utf-8"),
                f"{ticker}_quantvision_anomalies.csv",
            )


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
                "Sharpe": float((r.mean() / r.std(ddof=0) * np.sqrt(252)) if r.std(ddof=0) > 0 else 0),
                "Max Drawdown %": float(drawdowns[ticker].min() * 100),
            }
        )

    st.dataframe(pd.DataFrame(summary_rows), width="stretch")
    st.plotly_chart(build_comparison_chart(compare_df, "Multi-Asset Price Comparison"), width="stretch")
    st.plotly_chart(build_comparison_chart(cumulative, "Cumulative Return Comparison"), width="stretch")
    st.markdown("### Correlation Matrix")
    st.dataframe(returns.corr(), width="stretch")


def _render_portfolio(market_data: dict[str, pd.DataFrame], username: str) -> None:
    st.subheader("Portfolio Tracker")
    with st.form("portfolio_add_form"):
        cols = st.columns(4)
        ticker = cols[0].text_input("Ticker", value="AAPL").upper().strip()
        quantity = cols[1].number_input("Quantity", min_value=0.0, value=10.0, step=1.0)
        buy_price = cols[2].number_input("Buy Price", min_value=0.0, value=100.0, step=0.5)
        buy_date = cols[3].date_input("Buy Date", value=datetime.today()).isoformat()
        submitted = st.form_submit_button("Add Position")
        if submitted and ticker and quantity > 0 and buy_price > 0:
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
        name = st.text_input("Watchlist name", value="Technology")
        create = st.form_submit_button("Create / Get")
        if create and name.strip():
            watchlist_id = watchlist_service.create_watchlist(WatchlistInput(username=username, name=name))
            st.session_state["active_watchlist_id"] = watchlist_id
            st.success(f"Watchlist ready: {name}")

    watchlists = watchlist_service.list_watchlists(username)
    st.dataframe(watchlists, width="stretch")
    if watchlists.empty:
        return

    selected_id = int(
        st.selectbox("Active watchlist", options=watchlists["id"].tolist(), index=0, key="watchlist_id")
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


def _evaluate_alert_conditions(df: pd.DataFrame, rule_type: str, threshold: float | None) -> tuple[bool, str]:
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
        triggered = float(previous.get("MACD", 0)) <= float(previous.get("MACD_Signal", 0)) and float(
            current.get("MACD", 0)
        ) > float(current.get("MACD_Signal", 0))
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
        cols = st.columns(3)
        ticker = cols[0].text_input("Ticker", value="AAPL").upper().strip()
        rule_type = cols[1].selectbox("Rule Type", options=rule_types)
        threshold = cols[2].number_input("Threshold (optional)", value=5.0)
        create_rule = st.form_submit_button("Create Rule")
        if create_rule and ticker:
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
    st.dataframe(alerts_service.list_history(username), width="stretch")


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


def _render_risk(market_data: dict[str, pd.DataFrame], focus_ticker: str) -> None:
    st.subheader("Risk Analytics")
    if focus_ticker not in market_data:
        st.info("Load market data first.")
        return

    asset_df = market_data[focus_ticker]
    benchmark_options = [ticker for ticker in market_data.keys() if ticker != focus_ticker]
    benchmark_name = (
        st.selectbox("Benchmark", options=benchmark_options, index=0)
        if benchmark_options
        else ""
    )
    benchmark_returns = (
        market_data[benchmark_name]["Return"] if benchmark_name and benchmark_name in market_data else None
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
        "Return 1Y %": float(((df["Close"].iloc[-1] / df["Close"].tail(252).iloc[0]) - 1) * 100)
        if len(df) >= 252
        else float(((df["Close"].iloc[-1] / df["Close"].iloc[0]) - 1) * 100),
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
    tickers += [token.strip().upper() for token in custom_ticker.split(",") if token.strip()]
tickers = sorted(set(tickers))

start_date = st.sidebar.date_input("Start Date", value=datetime(2018, 1, 1))
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
    st.session_state["market_data"] = _load_market_data(tickers, start_date, end_date, uploaded_file)

market_data = st.session_state.get("market_data", {})
focus_ticker = st.sidebar.selectbox(
    "Focus ticker",
    options=list(market_data.keys()) if market_data else ["AAPL"],
)

if module == "Dashboard":
    _render_dashboard(market_data, focus_ticker)
elif module == "Anomalies":
    _render_anomalies(market_data, selected_methods, params)
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
elif module == "Admin":
    _render_admin()
