import streamlit as st
st.set_page_config(page_title="Stock Anomaly Detector", layout="wide")
import os
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from prophet import Prophet
from services.auth_service import AuthService

auth_service = AuthService(db_path='users.db')
auth_service.initialize()

# --- Login/Register Panel ---
def login_panel():
    st.markdown("<style>div[data-testid='column']:nth-of-type(2) {margin: auto;}</style>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<div style='text-align:center;'><h1>Login / Register</h1></div>", unsafe_allow_html=True)
        option = st.radio('Choose action:', ['Login', 'Register'], horizontal=True)
        if option == 'Register':
            st.subheader('Register')
            first_name = st.text_input('First Name')
            last_name = st.text_input('Last Name')
            username = st.text_input('Username')
            username_status = st.empty()
            if username:
                if not auth_service.is_username_available(username):
                    username_status.error('Username is not available.')
                else:
                    username_status.success('Username is available.')
            email = st.text_input('Email')
            email_status = st.empty()
            if email.strip():
                if not auth_service.is_email_available(email):
                    email_status.error('Email is already registered.')
                else:
                    email_status.success('Email is available.')
            password = st.text_input('Password', type='password')
            password2 = st.text_input('Repeat Password', type='password')
            if st.button('Register'):
                required_fields = [first_name, last_name, username, email, password, password2]
                if not all(field.strip() for field in required_fields):
                    st.error('All fields are required.')
                elif password != password2:
                    st.error('Passwords do not match.')
                elif not auth_service.is_strong_password(password):
                    st.error('Password must be at least 8 characters, include uppercase, lowercase, number, and special character.')
                elif not auth_service.is_username_available(username):
                    st.error('Username is not available.')
                elif not auth_service.is_email_available(email):
                    st.error('Email is already registered. Try logging in.')
                else:
                    registered, register_error = auth_service.register_user(username, email, first_name, last_name, password)
                    if registered:
                        st.success('Registration successful! Please log in.')
                        st.session_state['logged_in'] = False
                        st.session_state['username'] = username
                        st.session_state['login_mode'] = True
                        st.rerun()
                    else:
                        st.error(register_error or 'Registration failed. Please try again.')
        else:
            st.subheader('Login')
            user_or_email = st.text_input('Username or Email')
            password = st.text_input('Password', type='password')
            if st.button('Login'):
                # Only check credentials, not password strength
                if auth_service.authenticate_user(user_or_email, password):
                    username = auth_service.get_username_by_identifier(user_or_email) or user_or_email
                    session_id = auth_service.create_session(username)
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.session_state['session_id'] = session_id
                    st.success(f'Login successful! Welcome, {username}.')
                    st.rerun()
                else:
                    st.error('Invalid username/email or password.')

if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    login_panel()
    st.stop()

# --- Main App Content ---
if st.session_state.get('logged_in'):
    st.write(f"Welcome, {st.session_state.get('username', '')}!")
    if st.button('Logout'):
        st.session_state['logged_in'] = False
        st.session_state['username'] = ''
        st.session_state['session_id'] = ''
        st.success('You have been logged out.')
        st.rerun()

st.title("📈 Stock Anomaly Detector")
st.write("Detect anomalies in historical stock prices using statistical methods.")


# --- Sidebar Layout ---
st.sidebar.header("App Settings")

# --- CSV Upload ---
uploaded_file = st.sidebar.file_uploader("Upload your own CSV data", type=["csv"], help="Upload a CSV file with stock data (Date, Close, etc.)")
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
tickers = st.sidebar.multiselect("Stock Tickers", options=popular_tickers, default=["AAPL"], help="Choose one or more stock tickers to analyze.")
custom_ticker = st.sidebar.text_input("Or enter custom tickers (comma separated)", value="", help="Add custom tickers separated by commas.")
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
    help="Select one or more anomaly detection methods."
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
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    results = {}
    if user_data is not None:
        # Use uploaded data as a custom ticker
        results["USER_CSV"] = user_data
    for ticker in tickers:
        csv_path = os.path.join(data_dir, f"{ticker}_10y.csv")
        df = pd.DataFrame()
        need_download = True
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path, index_col=0, header=[0,1], parse_dates=True)
                if isinstance(df.columns, pd.MultiIndex):
                    df = df.xs(ticker, axis=1, level=1)
                    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
                # Check if data covers selected date range
                if not df.empty:
                    df_dates = pd.to_datetime(df.index)
                    if df_dates.min() <= pd.to_datetime(start_date) and df_dates.max() >= pd.to_datetime(end_date):
                        need_download = False
            except Exception:
                st.warning(f"Error reading cached data for {ticker}. Will re-download.")
        if need_download:
            with st.spinner(f"Downloading data for {ticker} from Yahoo Finance..."):
                try:
                    df = yf.download(ticker, start=start_date, end=end_date)
                    if not df.empty:
                        df.to_csv(csv_path)
                        st.success(f"Data for {ticker} downloaded and saved.")
                    else:
                        st.error(f"No data found for {ticker} in selected date range.")
                except Exception as e:
                    st.error(f"Failed to download data for {ticker}: {e}")
        if not df.empty:
            # Ensure 'Close' is a Series, not DataFrame
            close_col = df['Close']
            if not isinstance(close_col, pd.Series):
                close_col = close_col.squeeze()
            df['Close'] = pd.to_numeric(close_col, errors='coerce')
            df['Return'] = df['Close'].pct_change()
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
            # Handle MultiIndex columns for 'Close'
            close_col_name = 'Close'
            if isinstance(df.columns, pd.MultiIndex):
                for col in df.columns:
                    if col[0] == 'Close':
                        close_col_name = col
                        break
            y_data = df[close_col_name]
            if hasattr(y_data, 'values') and len(y_data) == len(df.index):
                fig1 = px.line(x=df.index, y=y_data, title=f'{ticker} Closing Price')
            else:
                fig1 = px.line(df, x=df.index, y='Close', title=f'{ticker} Closing Price')
            st.plotly_chart(fig1, width='stretch')

            st.header("Anomaly Detection")
            mask = df['Return'].notna()
            method_labels = []
            if "Z-Score" in selected_methods:
                mean, std = df['Return'].mean(), df['Return'].std()
                df['Anomaly_zscore'] = np.abs(df['Return'] - mean) > zscore_threshold * std
                method_labels.append(('Anomaly_zscore', 'Z-Score'))
            if "I-Forest" in selected_methods:
                iso = IsolationForest(contamination=iforest_contamination, random_state=42)
                df['Anomaly_iforest'] = False
                df.loc[mask, 'Anomaly_iforest'] = iso.fit_predict(df.loc[mask, ['Return']].values.reshape(-1,1)) == -1
                method_labels.append(('Anomaly_iforest', 'I-Forest'))
            if "DBSCAN" in selected_methods:
                db = DBSCAN(eps=dbscan_eps, min_samples=dbscan_min_samples)
                df['Anomaly_dbscan'] = False
                labels = db.fit_predict(df.loc[mask, ['Return']].values.reshape(-1,1))
                df.loc[mask, 'Anomaly_dbscan'] = labels == -1
                method_labels.append(('Anomaly_dbscan', 'DBSCAN'))
            if "Prophet" in selected_methods:
                try:
                    prophet_df = df[['Close']].reset_index()
                    prophet_df.columns = ['ds', 'y']
                    prophet_df['ds'] = pd.to_datetime(prophet_df['ds']).dt.tz_localize(None)
                    m = Prophet(daily_seasonality=True)
                    m.fit(prophet_df)
                    forecast = m.predict(m.make_future_dataframe(periods=0))
                    df['Prophet_yhat'] = forecast['yhat'].values
                    df['Prophet_resid'] = df['Close'].values - df['Prophet_yhat'].values
                    df['Anomaly_prophet'] = np.abs(df['Prophet_resid']) > 3 * df['Prophet_resid'].std()
                    method_labels.append(('Anomaly_prophet', 'Prophet'))
                except Exception as e:
                    st.warning(f"Prophet failed: {e}")
                    df['Anomaly_prophet'] = False
            if "Rolling Quantile" in selected_methods:
                # Rolling quantile anomaly detection
                df['Q_low'] = df['Close'].rolling(window=rolling_window, min_periods=1).quantile(quantile_low)
                df['Q_high'] = df['Close'].rolling(window=rolling_window, min_periods=1).quantile(quantile_high)
                df['Anomaly_rolling_quantile'] = (df['Close'] < df['Q_low']) | (df['Close'] > df['Q_high'])
                method_labels.append(('Anomaly_rolling_quantile', 'Rolling Quantile'))

            st.subheader("Anomaly Visualization (Selected Methods)")
            anomaly_df = df.copy()
            anomaly_df['Method'] = 'None'
            for col, label in method_labels:
                anomaly_df.loc[anomaly_df[col], 'Method'] = label
            pts = anomaly_df[anomaly_df['Method'] != 'None']
            # Fix scatter plot for MultiIndex and length mismatch
            scatter_close_col = 'Close'
            if isinstance(pts.columns, pd.MultiIndex):
                for col in pts.columns:
                    if col[0] == 'Close':
                        scatter_close_col = col
                        break
            y_pts = pts[scatter_close_col]
            if hasattr(y_pts, 'values') and len(y_pts) == len(pts.index):
                fig_final = px.scatter(x=pts.index, y=y_pts, color=pts['Method'], title="Anomalies Detected")
            else:
                fig_final = px.scatter(pts, x=pts.index, y='Close', color='Method', title="Anomalies Detected")
            fig_final.add_scatter(x=df.index, y=y_data, mode='lines', name='Price', opacity=0.3)
            st.plotly_chart(fig_final, width='stretch')

            # --- Export Plot as Image ---
            st.subheader("Export Visualization")
            import io
            img_bytes = fig_final.to_image(format="png") if hasattr(fig_final, "to_image") else None
            if img_bytes:
                st.download_button("Download Plot as PNG", img_bytes, f"{ticker}_anomalies.png", mime="image/png")
            else:
                st.info("Image export not supported in this environment. Try running locally with plotly >=5.0.")

            # --- Method Comparison & Benchmarking ---
            st.subheader("Method Comparison & Benchmarking")
            import time
            comparison = []
            for col, label in method_labels:
                start = time.time()
                anomaly_count = int(df[col].sum())
                # Simple benchmarking: run method again and time it
                if label == 'Z-Score':
                    _ = np.abs(df['Return'] - df['Return'].mean()) > zscore_threshold * df['Return'].std()
                elif label == 'I-Forest':
                    iso = IsolationForest(contamination=iforest_contamination, random_state=42)
                    _ = iso.fit_predict(df.loc[mask, ['Return']].values.reshape(-1,1)) == -1
                elif label == 'DBSCAN':
                    db = DBSCAN(eps=dbscan_eps, min_samples=dbscan_min_samples)
                    _ = db.fit_predict(df.loc[mask, ['Return']].values.reshape(-1,1)) == -1
                elif label == 'Prophet':
                    try:
                        prophet_df = df[['Close']].reset_index()
                        prophet_df.columns = ['ds', 'y']
                        prophet_df['ds'] = pd.to_datetime(prophet_df['ds']).dt.tz_localize(None)
                        m = Prophet(daily_seasonality=True)
                        m.fit(prophet_df)
                        forecast = m.predict(m.make_future_dataframe(periods=0))
                        resid = df['Close'].values - forecast['yhat'].values
                        _ = np.abs(resid) > 3 * np.std(resid)
                    except:
                        pass
                elapsed = time.time() - start
                comparison.append({
                    'Method': label,
                    'Anomalies': anomaly_count,
                    'Time (s)': round(elapsed, 3)
                })
            st.dataframe(pd.DataFrame(comparison))
            st.caption("This table compares the number of anomalies detected and the execution time for each method. Use it to evaluate which method is most sensitive or efficient for your data.")

            st.download_button(f"Download {ticker} CSV", df.to_csv().encode('utf-8'), f"{ticker}_anomalies.csv")
else:
    st.info("Select parameters and click 'Load Data'.")