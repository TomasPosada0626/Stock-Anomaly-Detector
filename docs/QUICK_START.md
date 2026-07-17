# QuantVision Quick Start (5 Minutes)

This quick start gets you from zero to a full anomaly analysis and downloadable report in under five minutes.

## What You Will Do
1. Start QuantVision locally with Docker Compose.
2. Login and open the anomaly lab.
3. Load market data and run anomaly detectors.
4. Export a report-ready dataset.

## 0) Prerequisites
- Docker Desktop installed and running.
- Port `8501` and `8000` available.

## 1) Start the Stack (about 60 seconds)

```bash
docker compose up --build
```

Services started:
- Streamlit UI: http://localhost:8501
- FastAPI API: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## 2) Login (about 30 seconds)
- Open the Streamlit UI.
- Register or login with your credentials.
- After authentication, the sidebar should display your role and workspace modules.

## 3) Load Data (about 60 seconds)
- In the sidebar, choose one or more tickers (`AAPL`, `MSFT`, `NVDA`).
- Set date range (default is fine).
- Click `Load / Refresh Market Data`.

You should now have dashboard metrics and charts available.

## 4) Detect Anomalies (about 90 seconds)
- Go to `Anomalies`.
- Select methods such as `Z-Score`, `I-Forest`, and `LOF`.
- Keep default hyperparameters for the first run.
- Inspect:
  - Price chart
  - Anomaly chart
  - Benchmark table (`Method`, `Anomalies`, `Time (s)`, `Parameters`)

## 5) Export Results (about 30 seconds)
- In the same anomalies tab, click `Export <TICKER> anomalies CSV`.
- Optionally open `Reports` and export PDF/CSV/PNG outputs.

## Quick Demo Flow (GIF-ready sequence)
Use this exact sequence if you want to record onboarding GIFs for portfolio presentation:
1. Login
2. Load market data
3. Open anomaly lab and run methods
4. Export report artifacts

## Troubleshooting
- No data loaded: verify internet access for market download and confirm ticker symbols.
- Login issue: remove local auth DB file and re-run app if needed.
- Docker port conflict: stop local processes using `8501` or `8000`.

## Next Steps
- See `docs/CASE_STUDIES.md` for concrete backtesting examples.
- See `docs/FEATURE_SHOWCASE.md` for visual tour and portfolio talking points.
