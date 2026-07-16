# Architecture

## Overview

This project is a single Streamlit application that combines UI and business logic in Python.

- Frontend/UI layer: Streamlit components in `src/app.py`
- Data access layer: Yahoo Finance download + local CSV cache
- Detection layer: statistical and ML methods
- Service layer: authentication and session logic in `src/services/auth_service.py`
- Persistence layer: local SQLite file (`users.db`) for user/session data

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
- `src/anomaly_methods.py`: reusable anomaly detection logic.
- `src/utils.py`: utility helpers for processing.
- `tests/test_anomaly_methods.py`: automated validation for anomaly algorithms.
- `tests/test_auth_integration.py`: integration tests for registration and login flows.

## Data Layout

- `data/`: local historical CSV files.
- `src/data/`: additional packaged sample data.
- `users.db`: local SQLite database generated at runtime (excluded from git).

## Deployment Topology

Current deployment model:
- Single container
- Single Streamlit process
- Port `8501`

There is no separate backend API service or separate frontend build pipeline in the current architecture.
