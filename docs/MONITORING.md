# Monitoring & Observability

## Health Checks
- `/health` - Liveness check
- `/health/detailed` - Full system status

## Metrics (Prometheus)
- `quantvision_anomalies_detected_total` - Anomalias por metodo
- `quantvision_logins_total` - Login attempts
- `quantvision_active_sessions` - Sesiones activas
- `quantvision_anomaly_detection_duration_seconds` - Latencia

## Logs
- Structured JSON logging
- Rotation diaria (30 dias retenidos)
- Levels: DEBUG, INFO, WARNING, ERROR

## Alerts
- Scheduler failures >3 consecutivas
- DB connection errors
- High error rate (>5% requests)
