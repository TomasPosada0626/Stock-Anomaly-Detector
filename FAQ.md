# FAQ - QuantVision

## General

**What does this app do?**
QuantVision is an intelligent financial analytics platform for market monitoring, anomaly detection,
technical analysis, portfolio tracking, alerts, risk analytics, reporting, and backtesting.

**Which methods are available?**
- Z-Score
- Isolation Forest
- DBSCAN
- Prophet
- Rolling Quantile
- Local Outlier Factor (LOF)
- One-Class SVM

**Which technical indicators are available?**
- RSI, MACD, SMA, EMA
- Bollinger Bands, VWAP
- ATR, ADX
- Ichimoku Cloud, OBV, Stochastic Oscillator

**Can I analyze more than one ticker?**
Yes. You can select multiple predefined tickers and add custom tickers.

**Can I upload my own CSV file?**
Yes. Use the sidebar uploader. Include at least date/time and price columns.

## Setup

**How do I run the app locally?**
1. Install dependencies: `pip install -r requirements.txt`
2. Start app: `streamlit run src/app.py`

**How do I run tests?**
Run `pytest` from repository root.

**How do I run quality checks?**
Run `ruff check src/services src/ui src/config tests src/api src/repositories scripts`.

## Deployment

**Is deployment supported?**
Yes. Docker deployment is ready, and cloud deployment is documented.

**What is the Docker command?**
- Build: `docker build -t quantvision .`
- Run: `docker run -p 8501:8501 quantvision`

**Is there CI/CD?**
Yes. CI validates tests, coverage, linting, and quality gates.

**Is there an API layer?**
Yes. FastAPI endpoints are available in `src/api/main.py`.

**Is there a scheduler for alerts?**
Yes. Use `python scripts/run_scheduler.py` or Task `scheduler:run`.

## Security and Sessions

**How are passwords stored?**
Passwords are hashed with bcrypt before storage.

**Where is user data stored?**
In local SQLite databases by default (`storage/users.db` and `storage/quantvision.db`).
Optional SQLAlchemy adapter support is available via `DATABASE_URL`.

## Troubleshooting

**Ticker data is not loading.**
Check ticker symbol, internet connection, and selected date range.

**Image export is failing.**
Verify Plotly + Kaleido are installed and compatible.

**Streamlit does not start.**
Confirm virtual environment activation and dependency installation.

**How do I run the scheduler manually?**
`python scripts/run_scheduler.py`

**How do I verify platform health?**
Use API endpoints `/health` and `/health/detailed`.

## Contact

For issues, suggestions, or collaboration:
- Open a GitHub issue
- Contact the repository author
