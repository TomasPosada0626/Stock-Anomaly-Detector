# Development Guide

This document standardizes local development, testing, and troubleshooting for QuantVision contributors.

## Local Setup
Preferred one-command setup:

```bash
bash scripts/setup_local.sh
```

Manual setup:

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements/lock.txt
```

## Common Commands
Using Taskfile:
- `task bootstrap`
- `task run`
- `task test`
- `task quality`
- `task e2e`

Using Makefile:
- `make dev`
- `make test`
- `make lint`
- `make coverage`

## Pre-commit Hooks
Install and enable:

```bash
pip install pre-commit
pre-commit install
```

Hooks configured in `.pre-commit-config.yaml`:
- Ruff lint/fix and format
- Black format
- Basic YAML/whitespace/large-file checks

## Dev Container
A one-click VS Code container setup is available at:
- `.devcontainer/devcontainer.json`

Features:
- Python 3.11 dev environment
- Docker-in-Docker support
- Forwarded ports 8501 and 8000

## Test Strategy
- Unit/integration tests under `tests/`
- E2E tests under `tests/e2e/`
- Coverage gate managed via CI and Codecov

## Troubleshooting
- `pytest` unknown cov args: install `pytest-cov` in active environment.
- Playwright missing browser: run `python -m playwright install chromium`.
- API auth issues: ensure same runtime DB and environment variables.
- Scheduler issues: inspect `storage/logs` and heartbeat JSON configured by env.
