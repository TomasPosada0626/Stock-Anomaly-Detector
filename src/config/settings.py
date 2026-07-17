import os
from pathlib import Path

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _positive(name: str, value: int) -> int:
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _resolve_project_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((PROJECT_ROOT / path).resolve())


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SESSION_TTL_MINUTES = _positive("SESSION_TTL_MINUTES", _int_env("SESSION_TTL_MINUTES", 60))
MAX_FAILED_LOGIN_ATTEMPTS = _positive(
    "MAX_FAILED_LOGIN_ATTEMPTS", _int_env("MAX_FAILED_LOGIN_ATTEMPTS", 5)
)
LOCKOUT_MINUTES = _positive("LOCKOUT_MINUTES", _int_env("LOCKOUT_MINUTES", 15))
USERS_DB_PATH = _resolve_project_path(os.getenv("USERS_DB_PATH", "storage/users.db"))
APP_LOG_DIR = _resolve_project_path(os.getenv("APP_LOG_DIR", "storage/logs"))
DATABASE_URL = os.getenv(
    "DATABASE_URL", f"sqlite:///{_resolve_project_path('storage/quantvision.db')}"
)
SCHEDULER_INTERVAL_MINUTES = _positive(
    "SCHEDULER_INTERVAL_MINUTES", _int_env("SCHEDULER_INTERVAL_MINUTES", 15)
)
MARKET_DATA_CACHE_TTL_SECONDS = _positive(
    "MARKET_DATA_CACHE_TTL_SECONDS", _int_env("MARKET_DATA_CACHE_TTL_SECONDS", 900)
)
USE_SQLALCHEMY_REPOSITORIES = _bool_env("USE_SQLALCHEMY_REPOSITORIES", False)
SCHEDULER_RUN_CONTINUOUS = _bool_env("SCHEDULER_RUN_CONTINUOUS", True)
STREAMLIT_APP_URL = os.getenv("STREAMLIT_APP_URL", "https://quantvision-tomas.streamlit.app/")

if ENVIRONMENT == "production":
    USERS_DB_PATH = _resolve_project_path(_required_env("USERS_DB_PATH"))
    APP_LOG_DIR = _resolve_project_path(_required_env("APP_LOG_DIR"))
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{USERS_DB_PATH}")
    STREAMLIT_APP_URL = _required_env("STREAMLIT_APP_URL")
