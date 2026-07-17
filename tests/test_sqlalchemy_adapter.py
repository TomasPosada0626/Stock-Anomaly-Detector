import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from repositories import sqlalchemy_adapter as adapter_module
from repositories.sqlalchemy_adapter import SqlAlchemyAdapter


def test_sqlalchemy_adapter_ping_returns_structured_health() -> None:
    adapter = SqlAlchemyAdapter(database_url="sqlite:///storage/quantvision_test.db")
    status = adapter.ping()
    assert hasattr(status, "ok")
    assert hasattr(status, "message")
    assert isinstance(status.enabled, bool)
    engine = adapter.get_engine()
    if engine is not None:
        engine.dispose()


def test_sqlalchemy_adapter_disabled_when_dependency_missing(monkeypatch) -> None:
    monkeypatch.setattr(adapter_module, "create_engine", None)
    adapter = SqlAlchemyAdapter(database_url="sqlite:///storage/quantvision_test.db")
    status = adapter.ping()
    assert status.enabled is False
    assert status.ok is False


def test_sqlalchemy_adapter_engine_unavailable_branch(monkeypatch) -> None:
    if adapter_module.create_engine is None:
        pytest.skip("SQLAlchemy dependency not installed")
    adapter = SqlAlchemyAdapter(database_url="sqlite:///storage/quantvision_test.db")
    monkeypatch.setattr(adapter, "get_engine", lambda: None)
    status = adapter.ping()
    assert status.available is False
    assert status.ok is False
    assert status.message == "Engine unavailable"


def test_sqlalchemy_adapter_ping_failure_branch(monkeypatch) -> None:
    if adapter_module.create_engine is None:
        pytest.skip("SQLAlchemy dependency not installed")

    class _BrokenConnect:
        def __enter__(self):
            raise RuntimeError("db down")

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeEngine:
        class dialect:  # noqa: D106 - test-only helper
            name = "sqlite"

        def connect(self):
            return _BrokenConnect()

    adapter = SqlAlchemyAdapter(database_url="sqlite:///storage/quantvision_test.db")
    monkeypatch.setattr(adapter, "get_engine", lambda: _FakeEngine())
    status = adapter.ping()
    assert status.enabled is True
    assert status.available is True
    assert status.ok is False
    assert "db down" in status.message
