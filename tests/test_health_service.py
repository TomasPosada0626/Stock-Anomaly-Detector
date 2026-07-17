import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from services.health_service import HealthService


def test_health_service_returns_status_and_checks() -> None:
    health = HealthService()
    result = health.run_checks()
    assert "status" in result
    assert "checks" in result
    assert isinstance(result["checks"], list)
    assert len(result["checks"]) >= 2
