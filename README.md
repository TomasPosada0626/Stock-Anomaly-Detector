# QuantVision

[![CI](https://github.com/TomasPosada0626/QuantVision/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/TomasPosada0626/QuantVision/actions/workflows/ci.yml?query=branch%3Amain)
[![Coverage](https://codecov.io/gh/TomasPosada0626/QuantVision/graph/badge.svg)](https://codecov.io/gh/TomasPosada0626/QuantVision)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Docker](https://img.shields.io/badge/Docker-Container-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![pytest](https://img.shields.io/badge/pytest-Tests-0A9EDC?logo=pytest&logoColor=white)](https://pytest.org/)
[![Ruff](https://img.shields.io/badge/Ruff-Lint-46A6F7?logo=ruff&logoColor=white)](https://docs.astral.sh/ruff/)
[![Black](https://img.shields.io/badge/Black-Formatter-000000?logo=python&logoColor=white)](https://black.readthedocs.io/)
[![Bandit](https://img.shields.io/badge/Bandit-SAST-FE7A16)](https://bandit.readthedocs.io/)
[![Playwright](https://img.shields.io/badge/Playwright-E2E-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/)

**Financial Intelligence Platform for Market Analysis, Risk Analytics and Strategy Backtesting**

QuantVision is a production-grade financial intelligence platform that combines quantitative analysis, machine learning, portfolio management, technical indicators and risk analytics into a unified experience for investors and financial analysts.

Designed following enterprise-grade software engineering practices including Clean Architecture, SOLID principles, automated testing, CI/CD pipelines, secure authentication and production deployment.

## Live Demo
- Application URL: https://quantvision-ia.streamlit.app/

## Author
- Tomas Posada ([GitHub](https://github.com/TomasPosada0626))

## Product Vision
QuantVision helps analysts and investors:
- Monitor market behavior through professional dashboards.
- Detect outliers using statistical and machine learning models.
- Compare assets with return, volatility, correlation, and drawdown analytics.
- Manage portfolios, watchlists, and actionable alert workflows.
- Evaluate strategies with a backtesting engine and benchmark against Buy & Hold.

## Architecture
The project follows a modular service-driven structure:
- `src/app.py`: Streamlit application entrypoint.
- `src/services`: business services (auth, market data, indicators, risk, portfolio, alerts, watchlists, backtesting).
- `src/ui`: reusable visual components and Plotly chart builders.
- `src/config`: typed runtime settings and environment-aware configuration.
- `src/anomaly_methods.py`: anomaly ML/statistical methods.
- `tests`: unit, integration, smoke, and e2e suites.

Design principles:
- Separation of concerns and high cohesion.
- Explicit interfaces between UI and service layers.
- Extensible modules for new asset classes and analytics features.

## Core Technologies
- Languages:
  - Python 3.11+
  - SQL (SQLite and PostgreSQL dialects via SQLAlchemy)
- Application Frameworks:
  - Streamlit (interactive product UI)
  - FastAPI + Uvicorn (API layer and service endpoints)
- Data and Quant Stack:
  - Pandas, NumPy
  - Scikit-Learn
  - Prophet
  - yfinance
- Visualization and Reporting:
  - Plotly
  - Kaleido (image export pipeline)
- Persistence and Data Access:
  - SQLite (local/dev state)
  - PostgreSQL (production persistence)
  - SQLAlchemy (repository abstraction + schema migrations/versioning)
- Scheduling and Operations:
  - APScheduler
  - Dedicated scheduler worker mode with heartbeat + restart policy controls
- Security and Auth:
  - bcrypt password hashing
  - Session-based authentication and RBAC enforcement
  - Login lockout controls + audit logging
- Testing and Quality:
  - pytest, pytest-cov
  - Ruff, Black
  - Bandit, pip-audit
  - Playwright (E2E smoke)
- Packaging and Runtime:
  - Docker
  - GitHub Actions (CI/CD)

## Feature Map
- Authentication with secure sessions, lockout policy, and audit events.
- Role-based access control (Admin, Analyst, Guest) with module-level gating.
- Professional market dashboard with KPI cards and advanced charts.
- Candlestick, volume, and multi-asset comparison visualizations.
- Technical indicators:
  - RSI, MACD, SMA, EMA, Bollinger Bands, VWAP, ATR, ADX,
  - Ichimoku Cloud, OBV, Stochastic Oscillator.
- Anomaly detection:
  - Z-Score, Isolation Forest, DBSCAN, Prophet, Rolling Quantile,
  - Local Outlier Factor (LOF), One-Class SVM.
- Portfolio tracker with invested capital, current value, PnL, and ROI.
- Watchlist management with persistent custom lists.
- Alert rules and alert history.
- Scheduled alert evaluation service for recurring scans.
- Backtesting engine with trade, win-rate, drawdown, and benchmark metrics.
- Notebook-to-production strategy pipeline service.
- Multi-factor portfolio optimization module.
- Report center with PDF, CSV, and PNG exports.
- Risk analytics:
  - Sharpe, Sortino, Maximum Drawdown, Volatility, Beta, Alpha, Correlation, VaR.
- FastAPI layer for health checks and portfolio/alerts endpoints.

## News Intelligence
- Yes, this is absolutely possible and highly recommended.
- Trigger: when an anomaly is detected for a ticker, fetch same-day finance news for that company.
- Goal: provide context for anomaly interpretation and faster analyst decision-making.
- Example flow:
  - Tesla anomaly detected
  - News retrieval for TSLA (same day window)
  - Context shown in UI, for example: "Tesla announces new autonomous driving release."
- Initial implementation does not require AI:
  - Integrate a financial news API and map by ticker/company.
  - Suggested providers: Finnhub, Alpha Vantage News, MarketAux, NewsAPI (finance-filtered queries).
  - Add service module (for example `src/services/news_service.py`) plus UI panel in dashboard/anomaly views.

## Use Cases
- Buy-side technical analysis workflow.
- Retail portfolio monitoring and anomaly-based screening.
- Quant experimentation and model comparison.
- Interview-ready FinTech engineering portfolio demonstration.

## Installation
### Local Environment
```bash
python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run src/app.py
```

### Run Modes (Current)
Frontend (Streamlit):
```bash
streamlit run src/app.py
```

API (FastAPI):
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

Scheduler worker (for cloud/background processing):
```bash
python scripts/run_scheduler.py
```

Recommended production flags for worker mode:
- `SCHEDULER_WORKER_MODE=true`
- `SCHEDULER_INTERVAL_MINUTES=15`
- `SCHEDULER_MAX_CYCLES=0`
- `SCHEDULER_MAX_CONSECUTIVE_FAILURES=10`
- `SCHEDULER_HEARTBEAT_FILE=storage/logs/scheduler_heartbeat.json`

### Docker
```bash
docker build -t quantvision .
docker run -p 8501:8501 quantvision
```

## Configuration
Main env variables:
- `ENVIRONMENT`
- `USERS_DB_PATH`
- `APP_LOG_DIR`
- `STREAMLIT_APP_URL`
- `SESSION_TTL_MINUTES`
- `MAX_FAILED_LOGIN_ATTEMPTS`
- `LOCKOUT_MINUTES`
- `SCHEDULER_INTERVAL_MINUTES`
- `SCHEDULER_RUN_CONTINUOUS`
- `SCHEDULER_WORKER_MODE`
- `SCHEDULER_MAX_CYCLES`
- `SCHEDULER_MAX_CONSECUTIVE_FAILURES`
- `SCHEDULER_HEARTBEAT_FILE`
- `USE_SQLALCHEMY_REPOSITORIES`
- `DATABASE_URL`

Reference examples:
- `config/env/.env.development.example`
- `config/env/.env.production.example`

Persistence mode:
- `USE_SQLALCHEMY_REPOSITORIES=false`: SQLite-native repositories in service layer.
- `USE_SQLALCHEMY_REPOSITORIES=true`: SQLAlchemy repositories via `DATABASE_URL`.

PostgreSQL production bootstrap:
- Install dependencies: `pip install -r requirements.txt`
- Set environment:
  - `USE_SQLALCHEMY_REPOSITORIES=true`
  - `DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<db_name>`
- Run schema bootstrap/versioning:
  - `python scripts/bootstrap_postgres.py`
- Migration state is tracked in table `schema_migrations`.
- Domain schema versioning entrypoint: `src/repositories/sqlalchemy_migrations.py`.

Scheduler fallback mode:
- APScheduler available: interval jobs in process.
- APScheduler unavailable and `SCHEDULER_RUN_CONTINUOUS=true`: continuous all-users loop.
- APScheduler unavailable and `SCHEDULER_RUN_CONTINUOUS=false`: single all-users pass and exit.

Scheduler worker mode (recommended for cloud worker dynos/containers):
- `SCHEDULER_WORKER_MODE=true`
- `SCHEDULER_INTERVAL_MINUTES=15`
- `SCHEDULER_MAX_CYCLES=0` (0 = infinite)
- `SCHEDULER_MAX_CONSECUTIVE_FAILURES=10`
- `SCHEDULER_HEARTBEAT_FILE=storage/logs/scheduler_heartbeat.json`
- Run worker process: `python scripts/run_scheduler.py`

## Security
- Password hashing via bcrypt.
- Login lockout after repeated failures.
- Session TTL and invalidation.
- Authentication audit trail.

## Testing and Quality
```bash
pytest
pytest --cov=src --cov-report=term-missing
ruff check src tests
black --check src tests
```

Quality expectations:
- High test coverage target (>=95%).
- CI gates for tests, lint, formatting, and security scans.

## CI/CD
GitHub Actions validates:
- Unit/integration/smoke tests
- Coverage threshold
- Lint and format
- Security checks
- E2E smoke flow

## Reports and Exports
- Executive PDF report generation.
- CSV export of analysis datasets.
- PNG export of visualizations.
- Structured analytics tables for executive and technical reporting workflows.

## API Layer
FastAPI entrypoint:
- `src/api/main.py`

Current endpoints:
- `GET /health`
- `GET /health/detailed`
- `GET /metrics`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /users/{username}/role`
- `GET /users/{username}/portfolio/summary`
- `GET /users/{username}/portfolio/positions`
- `POST /users/{username}/portfolio/positions`
- `DELETE /users/{username}/portfolio/positions/{position_id}`
- `GET /users/{username}/alerts/history`
- `GET /users/{username}/alerts/rules`
- `POST /users/{username}/alerts/rules`
- `DELETE /users/{username}/alerts/rules/{rule_id}`
- `GET /users/{username}/watchlists`
- `POST /users/{username}/watchlists`
- `DELETE /users/{username}/watchlists/{watchlist_id}`
- `GET /users/{username}/watchlists/{watchlist_id}/items`
- `POST /users/{username}/watchlists/{watchlist_id}/items`
- `DELETE /users/{username}/watchlists/{watchlist_id}/items/{ticker}`

## Deployment
See:
- `docs/operations/DEPLOYMENT.md`
- `docs/operations/RUNBOOK.md`

## Roadmap
- Strategy governance policies (approval workflows, rollback controls).
- Factor model monitoring and drift alerting.
- Scenario-based stress optimization constraints.

## Benchmarks
The anomaly lab includes method-level execution timing and anomaly counts,
allowing direct benchmark comparisons across selected detection models.

## Application Flow
```mermaid
flowchart LR
    A[Login / Session Validation] --> B[Market Data Ingestion]
    B --> C[Indicators + Returns Engine]
    C --> D[Anomaly Detection Lab]
    C --> E[Risk Analytics]
    C --> F[Portfolio & Watchlists]
    D --> G[Alerts Engine]
    D --> H[Backtesting Engine]
    E --> I[Reporting / Exports]
    F --> I
    G --> I
    H --> I
```

## Documentation
- `docs/architecture/ARCHITECTURE.md`
- `docs/guides/FAQ.md`
- `docs/operations/DEPLOYMENT.md`
- `docs/operations/RUNBOOK.md`

## License
MIT. See `LICENSE`.
