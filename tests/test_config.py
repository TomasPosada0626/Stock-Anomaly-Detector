import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


@pytest.fixture(autouse=True)
def clear_config_cache() -> None:
    sys.modules.pop("config", None)
    sys.modules.pop("config.settings", None)


def test_config_package_exports_expected_symbols() -> None:
    config_pkg = importlib.import_module("config")
    exported = set(getattr(config_pkg, "__all__", []))

    assert "SESSION_TTL_MINUTES" in exported
    assert "MAX_FAILED_LOGIN_ATTEMPTS" in exported
    assert "LOCKOUT_MINUTES" in exported
    assert "STREAMLIT_APP_URL" in exported


def test_bool_environment_flags_are_parsed(monkeypatch) -> None:
    monkeypatch.setenv("USE_SQLALCHEMY_REPOSITORIES", "true")
    monkeypatch.setenv("SCHEDULER_RUN_CONTINUOUS", "0")

    settings = importlib.import_module("config.settings")

    assert settings.USE_SQLALCHEMY_REPOSITORIES is True
    assert settings.SCHEDULER_RUN_CONTINUOUS is False
