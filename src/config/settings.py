import os


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


SESSION_TTL_MINUTES = _int_env("SESSION_TTL_MINUTES", 60)
MAX_FAILED_LOGIN_ATTEMPTS = _int_env("MAX_FAILED_LOGIN_ATTEMPTS", 5)
LOCKOUT_MINUTES = _int_env("LOCKOUT_MINUTES", 15)
USERS_DB_PATH = os.getenv("USERS_DB_PATH", "storage/users.db")
APP_LOG_DIR = os.getenv("APP_LOG_DIR", "storage/logs")
STREAMLIT_APP_URL = os.getenv(
    "STREAMLIT_APP_URL", "https://stock-anomaly-detector-tomas.streamlit.app/"
)
