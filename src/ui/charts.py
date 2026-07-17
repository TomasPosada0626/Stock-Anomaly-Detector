import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _resolve_close_column(df: pd.DataFrame):
    close_col_name = "Close"
    if isinstance(df.columns, pd.MultiIndex):
        for col in df.columns:
            if col[0] == "Close":
                close_col_name = col
                break
    return close_col_name


def build_price_chart(df: pd.DataFrame, ticker: str):
    close_col_name = _resolve_close_column(df)
    y_data = df[close_col_name]
    if hasattr(y_data, "values") and len(y_data) == len(df.index):
        return px.line(x=df.index, y=y_data, title=f"{ticker} Closing Price"), y_data
    return px.line(df, x=df.index, y="Close", title=f"{ticker} Closing Price"), df["Close"]


def build_anomaly_chart(df: pd.DataFrame, pts: pd.DataFrame, y_data):
    scatter_close_col = _resolve_close_column(pts)
    y_pts = pts[scatter_close_col]
    if hasattr(y_pts, "values") and len(y_pts) == len(pts.index):
        fig_final = px.scatter(
            x=pts.index, y=y_pts, color=pts["Method"], title="Anomalies Detected"
        )
    else:
        fig_final = px.scatter(
            pts, x=pts.index, y="Close", color="Method", title="Anomalies Detected"
        )
    fig_final.add_scatter(x=df.index, y=y_data, mode="lines", name="Price", opacity=0.3)
    return fig_final


def build_candlestick_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name=ticker,
            )
        ]
    )
    fig.update_layout(
        template="plotly_dark",
        title=f"{ticker} Candlestick",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )
    return fig


def build_volume_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Bar(
                x=df.index,
                y=df["Volume"],
                marker_color="#4a90e2",
                name="Volume",
            )
        ]
    )
    fig.update_layout(
        template="plotly_dark",
        title=f"{ticker} Volume",
        hovermode="x unified",
    )
    return fig


def build_comparison_chart(df: pd.DataFrame, title: str) -> go.Figure:
    fig = go.Figure()
    for col in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], mode="lines", name=str(col)))
    fig.update_layout(template="plotly_dark", title=title, hovermode="x unified")
    return fig
