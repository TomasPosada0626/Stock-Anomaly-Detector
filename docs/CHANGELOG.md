# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]
- Documentation refactor: simplified and standardized `README.md`.
- Added dedicated docs: `DEPLOYMENT.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`.
- Updated `FAQ.md` with consistent run and deployment guidance.
- Improved contributor and project guidance for portfolio/recruiter readability.
- Reorganized repository structure with `docs/` and `scripts/` directories.
- Consolidated historical CSV samples under `data/` and removed duplicated `src/data/`.
- Standardized runtime artifacts under `storage/` paths (`storage/users.db`, `storage/logs/`).

## [2026-02-03]
- Initial release: anomaly detection app for financial time series.
- Added login/registration and session management with SQLite.
- Implemented methods: Z-Score, Isolation Forest, DBSCAN, Prophet, Rolling Quantile.
- Added benchmarking, CSV/image export, and analysis notebooks.
- Added Dockerfile, FAQ, and automated tests.
