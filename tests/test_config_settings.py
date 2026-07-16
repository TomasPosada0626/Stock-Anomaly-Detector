import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


@pytest.fixture(autouse=True)
def clear_config_module_cache() -> None:
    sys.modules.pop("config.settings", None)


def test_default_environment_is_development(monkeypatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    settings = importlib.import_module("config.settings")
    assert settings.ENVIRONMENT == "development"


def test_production_requires_critical_env(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("USERS_DB_PATH", raising=False)
    monkeypatch.delenv("APP_LOG_DIR", raising=False)
    monkeypatch.delenv("STREAMLIT_APP_URL", raising=False)

    with pytest.raises(ValueError):
        importlib.import_module("config.settings")


def test_production_import_with_required_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("USERS_DB_PATH", str(tmp_path / "users.db"))
    monkeypatch.setenv("APP_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("STREAMLIT_APP_URL", "https://example.com")

    settings = importlib.import_module("config.settings")

    assert settings.ENVIRONMENT == "production"
    assert settings.USERS_DB_PATH.endswith("users.db")


def test_invalid_int_env_uses_default(monkeypatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("SESSION_TTL_MINUTES", "not-int")

    settings = importlib.import_module("config.settings")

    assert settings.SESSION_TTL_MINUTES == 60


def test_non_positive_setting_raises(monkeypatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("SESSION_TTL_MINUTES", "0")

    with pytest.raises(ValueError):
        importlib.import_module("config.settings")
