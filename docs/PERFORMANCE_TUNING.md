# Performance Tuning Guide

This document describes practical tuning controls implemented in QuantVision.

## Current Optimizations
- Database index migration v2 in `src/repositories/sqlalchemy_migrations.py`.
- UI pagination helper in `src/services/performance_service.py`.
- Alert and watchlist views limited to latest 50 rows in `src/app.py`.

## Database Indexes
Added composite indexes for common filters and sort patterns:
- `portfolio_positions (username, ticker, created_at)`
- `watchlists (username, created_at)`
- `watchlist_items (ticker, created_at)`
- `alert_rules (username, ticker, active)`
- `alert_rules (ticker, created_at)`
- `alert_history (username, triggered_at)`
- `alert_history (ticker, triggered_at)`

## Query Plan Inspection
Use:
- `explain_query_plan(engine, query)` from `src/repositories/sqlalchemy_migrations.py`

Example query to inspect:
- `SELECT * FROM alert_history WHERE username = 'alice' ORDER BY triggered_at DESC`

## App-Level Recommendations
- Keep default date windows bounded for expensive historical analysis.
- Avoid running all anomaly methods on too many tickers simultaneously.
- Run scheduler as a separate worker process.

## Next Performance Steps
- Add `st.cache_data` for deterministic indicator pipelines.
- Introduce async report generation queue for heavy PDF exports.
- Add explicit pagination controls in UI for large watchlists and alert history.
