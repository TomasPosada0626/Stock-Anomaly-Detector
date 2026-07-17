import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from repositories.sqlalchemy_adapter import SqlAlchemyAdapter


def test_sqlalchemy_adapter_ping_returns_structured_health() -> None:
    adapter = SqlAlchemyAdapter(database_url="sqlite:///storage/quantvision_test.db")
    status = adapter.ping()
    assert hasattr(status, "ok")
    assert hasattr(status, "message")
    assert isinstance(status.enabled, bool)
