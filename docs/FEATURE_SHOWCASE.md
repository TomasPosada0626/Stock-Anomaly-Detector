# QuantVision Feature Showcase

This showcase is structured as a visual story you can use in portfolio demos or interviews.

## 1) Executive Dashboard
What to show:
- Live price, volume, and valuation proxies
- Candlestick + volume + terminal multiview charts
- Fast comparison across selected tickers

Screenshot:
- `screenshots/1.png`

## 2) Anomaly Detection Lab
What to show:
- Multiple detectors in one workspace (`Z-Score`, `I-Forest`, `DBSCAN`, `Prophet`, `LOF`, `One-Class SVM`)
- Method benchmark table with runtime and anomaly counts
- One-click CSV export for downstream analysis

Screenshot:
- `screenshots/2.png`

## 3) Reports and Operational Outputs
What to show:
- Report center with PDF/CSV/PNG exports
- Backtesting metrics (return, win rate, drawdown, buy-and-hold)
- Operational readiness through API + scheduler services

Screenshot:
- `screenshots/3.png`

## Demo Narrative (2-3 minutes)
1. Open dashboard and explain market context.
2. Jump to anomaly lab and compare detector outputs.
3. Finish in reports with downloadable artifacts.

## Talking Points
- Built with Streamlit + FastAPI + SQLAlchemy repositories.
- High test discipline with CI gates and security scans.
- Designed as a production-ready portfolio, not only a notebook prototype.
