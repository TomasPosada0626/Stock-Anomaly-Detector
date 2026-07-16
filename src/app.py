import streamlit as st

st.set_page_config(page_title="Stock Anomaly Detector", layout="wide")
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from prophet import Prophet
from config import SESSION_TTL_MINUTES
from services.auth_service import AuthService
from services.market_data_service import add_return_features, get_ticker_data
from services.observability import get_logger
from ui.auth_ui import render_login_panel
from ui.charts import build_anomaly_chart, build_price_chart

logger = get_logger("app")
auth_service = AuthService(db_path="users.db")
auth_service.initialize()
logger.info("app_initialized")

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

# --- Main App Content ---
if st.session_state.get("logged_in"):
    st.write(f"Welcome, {st.session_state.get('username', '')}!")
    if st.button("Logout"):
        current_session_id = st.session_state.get("session_id", "")
        if current_session_id:
            auth_service.invalidate_session(current_session_id)
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.session_state["session_id"] = ""
        st.success("You have been logged out.")
        st.rerun()

st.title("📈 Stock Anomaly Detector")
st.write("Detect anomalies in historical stock prices using statistical methods.")


# --- Sidebar Layout ---
st.sidebar.header("App Settings")

# --- CSV Upload ---
uploaded_file = st.sidebar.file_uploader(
    "Upload your own CSV data",
    type=["csv"],
    help="Upload a CSV file with stock data (Date, Close, etc.)",
)
user_data = None
if uploaded_file is not None:
    try:
        user_data = pd.read_csv(uploaded_file, parse_dates=True)
        st.sidebar.success("CSV uploaded successfully!")
        st.sidebar.write(user_data.head())
    except Exception as e:
        st.sidebar.error(f"Error reading CSV: {e}")

st.sidebar.markdown("---")

st.sidebar.header("Select Stocks and Date Range")
popular_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "JPM", "V", "DIS"]
tickers = st.sidebar.multiselect(
    "Stock Tickers",
    options=popular_tickers,
    default=["AAPL"],
    help="Choose one or more stock tickers to analyze.",
)
custom_ticker = st.sidebar.text_input(
    "Or enter custom tickers (comma separated)",
    value="",
    help="Add custom tickers separated by commas.",
)
if custom_ticker:
    tickers += [t.strip().upper() for t in custom_ticker.split(",") if t.strip()]

start_date = st.sidebar.date_input("Start Date", value=datetime(2016, 1, 1))
end_date = st.sidebar.date_input("End Date", value=datetime(2026, 1, 1))

st.sidebar.markdown("---")
st.sidebar.header("Anomaly Detection Methods")
method_options = ["Z-Score", "I-Forest", "DBSCAN", "Prophet", "Rolling Quantile"]
selected_methods = st.sidebar.multiselect(
    "Select Methods",
    method_options,
    default=["Z-Score", "I-Forest"],
    help="Select one or more anomaly detection methods.",
)

# Parameter controls
zscore_threshold = st.sidebar.slider("Z-Score Threshold", 1.0, 5.0, 3.0, 0.1)
iforest_contamination = st.sidebar.slider("IForest Contamination", 0.001, 0.2, 0.01, 0.001)
dbscan_eps = st.sidebar.slider("DBSCAN eps", 0.01, 0.2, 0.03, 0.01)
dbscan_min_samples = st.sidebar.slider("DBSCAN min_samples", 2, 20, 5, 1)
rolling_window = st.sidebar.slider("Rolling Quantile Window", 5, 60, 20, 1)
quantile_low = st.sidebar.slider("Lower Quantile", 0.01, 0.2, 0.05, 0.01)
quantile_high = st.sidebar.slider("Upper Quantile", 0.8, 0.99, 0.95, 0.01)


# --- Multi-ticker and method comparison ---
if st.sidebar.button("Load Data"):
    data_dir = "data"
    results = {}
    if user_data is not None:
        # Use uploaded data as a custom ticker
        results["USER_CSV"] = user_data
    for ticker in tickers:
        try:
            df, downloaded, warning_message = get_ticker_data(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                data_dir=data_dir,
            )
            if downloaded and not df.empty:
                st.success(f"Data for {ticker} downloaded and saved.")
            if warning_message:
                st.warning(warning_message)
        except Exception as e:
            logger.exception("data_load_failed ticker=%s", ticker)
            st.error(f"Failed to load data for {ticker}: {e}")
            df = pd.DataFrame()
        if not df.empty:
            df = add_return_features(df)
            results[ticker] = df
        else:
            st.warning(f"No data for {ticker}.")

    if not results:
        st.error("No data loaded for any ticker.")
        st.stop()

    tabs = st.tabs([f"{ticker}" for ticker in results.keys()])
    for i, (ticker, df) in enumerate(results.items()):
        with tabs[i]:
            st.subheader(f"Raw Data for {ticker}")
            st.dataframe(df.tail(10))

            st.header("Exploratory Data Analysis (EDA)")
            st.markdown("**Basic Statistics**")
            st.write(df.describe())
            st.markdown("**Price Trend**")
            fig1, y_data = build_price_chart(df, ticker)
            st.plotly_chart(fig1, width="stretch")

            st.header("Anomaly Detection")
            mask = df["Return"].notna()
            method_labels = []
            if "Z-Score" in selected_methods:
                mean, std = df["Return"].mean(), df["Return"].std()
                df["Anomaly_zscore"] = np.abs(df["Return"] - mean) > zscore_threshold * std
                method_labels.append(("Anomaly_zscore", "Z-Score"))
            if "I-Forest" in selected_methods:
                iso = IsolationForest(contamination=iforest_contamination, random_state=42)
                df["Anomaly_iforest"] = False
                df.loc[mask, "Anomaly_iforest"] = (
                    iso.fit_predict(df.loc[mask, ["Return"]].values.reshape(-1, 1)) == -1
                )
                method_labels.append(("Anomaly_iforest", "I-Forest"))
            if "DBSCAN" in selected_methods:
                db = DBSCAN(eps=dbscan_eps, min_samples=dbscan_min_samples)
                df["Anomaly_dbscan"] = False
                labels = db.fit_predict(df.loc[mask, ["Return"]].values.reshape(-1, 1))
                df.loc[mask, "Anomaly_dbscan"] = labels == -1
                method_labels.append(("Anomaly_dbscan", "DBSCAN"))
            if "Prophet" in selected_methods:
                try:
                    prophet_df = df[["Close"]].reset_index()
                    prophet_df.columns = ["ds", "y"]
                    prophet_df["ds"] = pd.to_datetime(prophet_df["ds"]).dt.tz_localize(None)
                    m = Prophet(daily_seasonality=True)
                    m.fit(prophet_df)
                    forecast = m.predict(m.make_future_dataframe(periods=0))
                    df["Prophet_yhat"] = forecast["yhat"].values
                    df["Prophet_resid"] = df["Close"].values - df["Prophet_yhat"].values
                    df["Anomaly_prophet"] = (
                        np.abs(df["Prophet_resid"]) > 3 * df["Prophet_resid"].std()
                    )
                    method_labels.append(("Anomaly_prophet", "Prophet"))
                except Exception as e:
                    st.warning(f"Prophet failed: {e}")
                    df["Anomaly_prophet"] = False
            if "Rolling Quantile" in selected_methods:
                # Rolling quantile anomaly detection
                df["Q_low"] = (
                    df["Close"].rolling(window=rolling_window, min_periods=1).quantile(quantile_low)
                )
                df["Q_high"] = (
                    df["Close"]
                    .rolling(window=rolling_window, min_periods=1)
                    .quantile(quantile_high)
                )
                df["Anomaly_rolling_quantile"] = (df["Close"] < df["Q_low"]) | (
                    df["Close"] > df["Q_high"]
                )
                method_labels.append(("Anomaly_rolling_quantile", "Rolling Quantile"))

            st.subheader("Anomaly Visualization (Selected Methods)")
            anomaly_df = df.copy()
            anomaly_df["Method"] = "None"
            for col, label in method_labels:
                anomaly_df.loc[anomaly_df[col], "Method"] = label
            pts = anomaly_df[anomaly_df["Method"] != "None"]
            fig_final = build_anomaly_chart(df, pts, y_data)
            st.plotly_chart(fig_final, width="stretch")

            # --- Export Plot as Image ---
            st.subheader("Export Visualization")
            import io

            img_bytes = fig_final.to_image(format="png") if hasattr(fig_final, "to_image") else None
            if img_bytes:
                st.download_button(
                    "Download Plot as PNG", img_bytes, f"{ticker}_anomalies.png", mime="image/png"
                )
            else:
                st.info(
                    "Image export not supported in this environment. Try running locally with plotly >=5.0."
                )

            # --- Method Comparison & Benchmarking ---
            st.subheader("Method Comparison & Benchmarking")
            import time

            comparison = []
            for col, label in method_labels:
                start = time.time()
                anomaly_count = int(df[col].sum())
                # Simple benchmarking: run method again and time it
                if label == "Z-Score":
                    _ = (
                        np.abs(df["Return"] - df["Return"].mean())
                        > zscore_threshold * df["Return"].std()
                    )
                elif label == "I-Forest":
                    iso = IsolationForest(contamination=iforest_contamination, random_state=42)
                    _ = iso.fit_predict(df.loc[mask, ["Return"]].values.reshape(-1, 1)) == -1
                elif label == "DBSCAN":
                    db = DBSCAN(eps=dbscan_eps, min_samples=dbscan_min_samples)
                    _ = db.fit_predict(df.loc[mask, ["Return"]].values.reshape(-1, 1)) == -1
                elif label == "Prophet":
                    try:
                        prophet_df = df[["Close"]].reset_index()
                        prophet_df.columns = ["ds", "y"]
                        prophet_df["ds"] = pd.to_datetime(prophet_df["ds"]).dt.tz_localize(None)
                        m = Prophet(daily_seasonality=True)
                        m.fit(prophet_df)
                        forecast = m.predict(m.make_future_dataframe(periods=0))
                        resid = df["Close"].values - forecast["yhat"].values
                        _ = np.abs(resid) > 3 * np.std(resid)
                    except:
                        pass
                elapsed = time.time() - start
                comparison.append(
                    {"Method": label, "Anomalies": anomaly_count, "Time (s)": round(elapsed, 3)}
                )
            st.dataframe(pd.DataFrame(comparison))
            st.caption(
                "This table compares the number of anomalies detected and the execution time for each method. Use it to evaluate which method is most sensitive or efficient for your data."
            )

            st.download_button(
                f"Download {ticker} CSV", df.to_csv().encode("utf-8"), f"{ticker}_anomalies.csv"
            )
else:
    st.info("Select parameters and click 'Load Data'.")
