# Deployment Guide

This document describes how to deploy QuantVision locally, with Docker, and in cloud services.

## 1. Local Run (No Docker)

Prerequisites:
- Python 3.10+
- pip

Steps:
1. Create and activate a virtual environment.
2. Install dependencies.
3. Run the Streamlit app.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run src/app.py
```

App URL: http://localhost:8501

## 2. Docker

Build image:

```bash
docker build -t quantvision .
```

Run container:

```bash
docker run --rm -p 8501:8501 quantvision
```

App URL: http://localhost:8501

Optional: mount local data directory:

```bash
docker run --rm -p 8501:8501 -v ${PWD}/data:/app/data quantvision
```

Notes:
- On Windows PowerShell, `${PWD}` works for the current directory.
- The Docker entrypoint is already configured in Dockerfile: `streamlit run src/app.py`.

## 3. Streamlit Community Cloud

1. Push repository to GitHub.
2. Go to Streamlit Community Cloud.
3. Create a new app and select this repository.
4. Set main file path to `src/app.py`.
5. Deploy.

Important:
- Keep app dependencies in `requirements.txt` only.
- Deep-learning notebook dependencies are optional in `requirements/notebooks.txt` and should not be required for cloud app startup.
- This repository pins cloud Python runtime in `runtime.txt`.

## 4. Generic Cloud (Docker-based)

Any provider that runs containers (Azure, GCP, AWS, Render, Railway, Fly.io) can run this app.

Requirements:
- Build Docker image from repository root.
- Expose/route port 8501.
- Keep environment variable `STREAMLIT_SERVER_HEADLESS=true`.

## 5. Health and Runtime Checks

After deployment:
1. Open app URL.
2. Validate login/register view appears.
3. Load one ticker (for example `AAPL`).
4. Confirm chart rendering and anomaly detection tabs.

Scheduler runtime behavior:
- Uses APScheduler interval execution when dependency is installed.
- Falls back to continuous all-users loop when `SCHEDULER_RUN_CONTINUOUS=true`.
- Runs one all-users evaluation pass and exits when `SCHEDULER_RUN_CONTINUOUS=false`.

Persistence behavior:
- `USE_SQLALCHEMY_REPOSITORIES=false` keeps SQLite-native service repositories.
- `USE_SQLALCHEMY_REPOSITORIES=true` enables SQLAlchemy repositories and uses `DATABASE_URL`.

## 6. Current Deployment Status in This Repository

Implemented:
- Dockerfile for containerized deployment.
- Local run instructions.
- CI workflow for tests, quality, security, and coverage.
- CD workflow for deployment smoke checks after CI success on `main`.

Not yet implemented:
- Automatic provider-side deploy trigger from GitHub Actions.
- IaC templates (Terraform/Bicep/CloudFormation).
- Provider-specific manifest files.

## 7. Recommended Environment Variables

- `SCHEDULER_INTERVAL_MINUTES=15`
- `SCHEDULER_RUN_CONTINUOUS=true`
- `USE_SQLALCHEMY_REPOSITORIES=false`
- `DATABASE_URL=sqlite:///storage/quantvision.db`
