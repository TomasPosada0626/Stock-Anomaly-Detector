# FAQ - Stock Anomaly Detector

## General

**What does this app do?**
It detects anomalies in historical stock prices using statistical and machine learning methods.

**Which methods are available?**
- Z-Score
- Isolation Forest
- DBSCAN
- Prophet
- Rolling Quantile

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

## Deployment

**Is deployment supported?**
Yes. Docker deployment is ready, and cloud deployment is documented.

**What is the Docker command?**
- Build: `docker build -t stock-anomaly-detector .`
- Run: `docker run -p 8501:8501 stock-anomaly-detector`

**Is there CI/CD?**
Yes. CI validates tests/coverage/quality/security and CD runs deployment smoke checks.

## Security and Sessions

**How are passwords stored?**
Passwords are hashed with bcrypt. Legacy SHA-256 records are upgraded to bcrypt on successful login.

**Where is user data stored?**
In a local SQLite database file (`storage/users.db`).

## Troubleshooting

**Ticker data is not loading.**
Check ticker symbol, internet connection, and selected date range.

**Image export is failing.**
Verify Plotly + Kaleido are installed and compatible.

**Streamlit does not start.**
Confirm virtual environment activation and dependency installation.

## Contact

For issues, suggestions, or collaboration:
- Open a GitHub issue
- Contact the repository author
