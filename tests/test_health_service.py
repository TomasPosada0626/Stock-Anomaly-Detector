import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import services.health_service as health_module
from services.health_service import HealthService


def test_health_service_returns_status_and_checks() -> None:
    health = HealthService()
    result = health.run_checks()
    assert "status" in result
    assert "checks" in result
    assert isinstance(result["checks"], list)
    assert len(result["checks"]) >= 2


def test_health_service_degraded_when_users_db_fails(monkeypatch) -> None:
    health = HealthService()

    def _raise_connect(*args, **kwargs):
        raise RuntimeError("sqlite unavailable")

    monkeypatch.setattr(health_module.sqlite3, "connect", _raise_connect)
    result = health.run_checks()
    assert result["status"] == "degraded"


def test_health_service_logs_dir_not_writable(monkeypatch) -> None:
    health = HealthService()
    monkeypatch.setattr(health_module.os, "access", lambda path, mode: False)
    status = health._check_logs_dir()
    assert status.ok is False
    assert status.message == "not writable"


def test_health_service_logs_dir_exception(monkeypatch) -> None:
    health = HealthService()

    def _raise_makedirs(*args, **kwargs):
        raise RuntimeError("mkdir failed")

    monkeypatch.setattr(health_module.os, "makedirs", _raise_makedirs)
    status = health._check_logs_dir()
    assert status.ok is False
    assert "mkdir failed" in status.message


def test_health_service_sqlalchemy_component_message() -> None:
    health = HealthService()
    status = health._check_sqlalchemy()
    assert status.name == "sqlalchemy"
    assert "enabled=" in status.message
