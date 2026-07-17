# Monitoring and Observability

This guide defines the production-oriented monitoring setup for QuantVision.

## Objectives
- Detect runtime failures early.
- Track business metrics (anomalies and trades).
- Measure latency hotspots by method and service flow.
- Enable traceability for API and scheduled workflows.

## Runtime Metrics
QuantVision exposes an application metrics snapshot at:
- `GET /metrics`

Core counters and timings now include:
- `anomalies_detected_total`
- `trades_executed_total`
- `scheduler_failures_total`
- `anomaly_method_runtime_seconds` (timings)
- `ab_exposure` and `ab_conversion` event streams via analytics tracker
- Prometheus formatted endpoint: `GET /metrics/prometheus`

These metrics are recorded by:
- `src/services/anomaly_lab_service.py`
- `src/services/backtesting_service.py`
- `src/services/scheduler_service.py`

## Suggested Prometheus Mapping
If you run a Prometheus sidecar/scraper, map snapshot fields to gauges/counters:
- `quantvision_anomalies_detected_total{method="..."}`
- `quantvision_trades_executed_total`
- `quantvision_scheduler_failures_total`
- `quantvision_anomaly_method_runtime_seconds_avg{method="..."}`

## Tracing (OpenTelemetry)
Tracing utilities are available in:
- `src/observability/tracing.py`

Behavior:
- If OpenTelemetry packages are installed, tracing can initialize with OTLP exporter.
- If packages are missing, tracing degrades safely to no-op mode.

Recommended OTEL env vars:
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_SERVICE_NAME=quantvision-api`

## Alerting Rules (Suggested)
- Scheduler degradation: trigger alert if `scheduler_failures_total` increases by >= 3 in 10 minutes.
- Anomaly engine slowdown: alert when `anomaly_method_runtime_seconds` p95 exceeds baseline by 2x.
- API instability: alert on repeated `5xx` responses from `/health/detailed` checks.

## Dashboard Panels (Grafana)
Minimum dashboard:
1. API health status (`/health`, `/health/detailed`)
2. Anomalies detected per method (stacked counter)
3. Trades executed per hour/day
4. Scheduler failures over time
5. Method runtime average and p95 trend

Provisioning artifacts:
- Prometheus scrape config: `docs/monitoring/prometheus.yml`
- Grafana dashboard JSON: `docs/monitoring/grafana-dashboard.json`
- Prometheus alert rules: `docs/monitoring/prometheus-alert-rules.yml`

## Operations Workflow
1. Check `/health/detailed` for immediate subsystem failures.
2. Inspect `/metrics` counter/timing spikes.
3. Correlate with scheduler logs in `storage/logs`.
4. Use tracing spans (if enabled) to isolate slow service paths.

## Security Note
The API now includes baseline security headers and rate limiting.
Keep these controls enabled in all internet-facing environments.
