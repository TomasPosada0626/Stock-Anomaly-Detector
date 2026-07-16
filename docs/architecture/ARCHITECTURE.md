# Architecture

## Overview

This project is a single Streamlit application that combines UI and business logic in Python.

- Frontend/UI layer: Streamlit components in `src/app.py`
- UI helper layer: auth and chart helpers in `src/ui/`
- Data access layer: Yahoo Finance download + local CSV cache in `src/services/market_data_service.py`
- Detection layer: statistical and ML methods
- Service layer: authentication and session logic in `src/services/auth_service.py`
- Persistence layer: local SQLite file (`storage/users.db`) for user/session data
- Observability layer: structured logging helpers in `src/services/observability.py`
- Config layer: environment-driven settings in `src/config/settings.py`

## Runtime Flow

1. User opens app.
2. Login/Register flow validates credentials.
3. User selects tickers and parameters.
4. App loads local CSV cache or downloads data.
5. Selected anomaly methods run.
6. Results are visualized and can be exported.

## Main Modules

- `src/app.py`: Streamlit app, controls, visualization orchestration.
- `src/services/auth_service.py`: registration/login/session logic and SQLite persistence.
- `src/services/market_data_service.py`: cached market data loading/downloading and return feature engineering.
- `src/services/observability.py`: logging utilities for operational tracing.
- `src/ui/auth_ui.py`: login/register panel rendering.
- `src/ui/charts.py`: reusable Plotly chart builders.
- `src/anomaly_methods.py`: reusable anomaly detection logic.
- `src/utils.py`: utility helpers for processing.
- `tests/test_anomaly_methods.py`: automated validation for anomaly algorithms.
- `tests/test_auth_integration.py`: integration tests for registration and login flows.
- `tests/test_market_data_service.py`: tests for cache/download/data-prep paths.
- `tests/test_ui_charts.py`: tests for plotting helpers.

## Data Layout

- `data/`: local historical CSV files.
- `storage/users.db`: local SQLite database generated at runtime (excluded from git).
- `storage/logs/`: runtime application logs (excluded from git).

## Security Model

- Passwords are stored with bcrypt.
- Legacy SHA-256 hashes are auto-upgraded to bcrypt on successful login.
- Failed login attempts are rate-limited with temporary lockout.
- Sessions are time-limited and expired sessions are cleaned up.
- Session creation invalidates previous active sessions for the same user.
- CI includes static analysis (`bandit`) and dependency vulnerability checks (`pip-audit`).

## Deployment Topology

Current deployment model:
- Single container
- Single Streamlit process
- Port `8501`

There is no separate backend API service or separate frontend build pipeline in the current architecture.
