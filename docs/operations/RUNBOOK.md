# Operations Runbook

## Service
- App URL: https://quantvision-tomas.streamlit.app/
- Runtime: Streamlit Cloud
- Source branch: `main`

## PostgreSQL Bootstrap
1. Ensure `DATABASE_URL` points to PostgreSQL using psycopg driver:
  - `postgresql+psycopg://<user>:<password>@<host>:5432/<db_name>`
2. Enable SQLAlchemy repositories:
  - `USE_SQLALCHEMY_REPOSITORIES=true`
3. Run bootstrap/migrations:
  - `python scripts/bootstrap_postgres.py`
4. Verify migration version:
  - Query table `schema_migrations` and confirm latest version exists.

## Scheduler Worker (Cloud)
Recommended dedicated worker process configuration:
- `SCHEDULER_WORKER_MODE=true`
- `SCHEDULER_INTERVAL_MINUTES=15`
- `SCHEDULER_MAX_CYCLES=0` (infinite)
- `SCHEDULER_MAX_CONSECUTIVE_FAILURES=10`
- `SCHEDULER_HEARTBEAT_FILE=storage/logs/scheduler_heartbeat.json`

Launch command:
- `python scripts/run_scheduler.py`

Observability:
- Structured scheduler logs emitted by `scheduler_service`.
- Heartbeat file is updated every cycle with:
  - timestamp
  - cycle number
  - per-user trigger summary
  - last error (if any)

Restart policy:
- Run scheduler as a dedicated process/container with `restart: always` (or equivalent).
- If consecutive cycle failures reach `SCHEDULER_MAX_CONSECUTIVE_FAILURES`, worker exits intentionally.
- Orchestrator should restart it automatically.

## Health Checks
1. Open app URL and verify login screen loads.
2. Perform a login.
3. Load one ticker (for example `AAPL`) and verify chart rendering.

## CI/CD
- CI workflow: `.github/workflows/ci.yml`
- CD workflow: `.github/workflows/cd.yml`
- CI gates:
  - tests + coverage (minimum 95%)
  - ruff + black
  - bandit + pip-audit

## Common Failures

### CI test failure
1. Re-run tests locally: `pytest`
2. Fix failing tests and push.

### Coverage below threshold
1. Run: `pytest --cov=src --cov-report=term-missing`
2. Add/adjust tests for uncovered lines.

### Security job failure
1. Read Bandit artifact report.
2. Fix medium/high findings first.

### Streamlit app unavailable
1. Check Streamlit Cloud logs.
2. Reboot app from Streamlit Cloud dashboard.
3. Verify latest commit deployed.

### Scheduler worker unhealthy
1. Check scheduler logs for `scheduler_continuous_cycle_failed` events.
2. Inspect heartbeat file path from `SCHEDULER_HEARTBEAT_FILE`.
3. Validate database connectivity and credentials in `DATABASE_URL`.
4. Restart worker process/container.

## Rollback
1. Revert problematic commit on `main`.
2. Push revert commit.
3. Confirm CI passes and Streamlit app recovers.
