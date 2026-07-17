# Operations Runbook

## Service
- App URL: https://quantvision-tomas.streamlit.app/
- Runtime: Streamlit Cloud
- Source branch: `main`

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

## Rollback
1. Revert problematic commit on `main`.
2. Push revert commit.
3. Confirm CI passes and Streamlit app recovers.
