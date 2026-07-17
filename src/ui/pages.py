import pandas as pd
import streamlit as st

from services.anomaly_lab_service import run_anomaly_methods
from ui.charts import (
    build_anomaly_chart,
    build_candlestick_chart,
    build_price_chart,
    build_terminal_multiview,
    build_volume_chart,
)


def render_dashboard_page(market_data: dict[str, pd.DataFrame], focus_ticker: str) -> None:
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
    dividend_yield_proxy = max(
        0.0,
        min(8.0, float(df["Close"].pct_change().rolling(252).mean().iloc[-1] * 100)),
    )
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
    st.plotly_chart(build_terminal_multiview(df, focus_ticker), width="stretch")


def render_anomalies_page(
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
            modeled, points, benchmark = run_anomaly_methods(
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
