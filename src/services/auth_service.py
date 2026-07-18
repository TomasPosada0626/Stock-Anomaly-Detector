import hashlib
import os
import re
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any, Match, Optional, Tuple, cast

import bcrypt

from config import (
    DATABASE_URL,
    LOCKOUT_MINUTES,
    MAX_FAILED_LOGIN_ATTEMPTS,
    SESSION_TTL_MINUTES,
    USE_SQLALCHEMY_REPOSITORIES,
    USERS_DB_PATH,
)
from services.observability import get_logger, metric

SqlAuthRepository: Any

try:
    from repositories.sqlalchemy_domain_repositories import SqlAuthRepository as _SqlAuthRepository

    SqlAuthRepository = _SqlAuthRepository
except Exception:  # pragma: no cover - optional dependency
    SqlAuthRepository = None

ALLOWED_ROLES = {"ADMIN", "ANALYST", "GUEST"}
MODULE_ACCESS_POLICY = {
    "ADMIN": {
        "Dashboard",
        "Anomalies",
        "AI Lab",
        "Governance",
        "Analytics",
        "Comparison",
        "Portfolio",
        "Watchlists",
        "Alerts",
        "Backtesting",
        "Risk",
        "Reports",
        "Admin",
    },
    "ANALYST": {
        "Dashboard",
        "Anomalies",
        "AI Lab",
        "Governance",
        "Analytics",
        "Comparison",
        "Portfolio",
        "Watchlists",
        "Alerts",
        "Backtesting",
        "Risk",
        "Reports",
    },
    "GUEST": {"Dashboard", "Comparison", "Risk", "Reports", "Analytics"},
}


class AuthService:
    def __init__(
        self,
        db_path: str = USERS_DB_PATH,
        use_sqlalchemy: bool = USE_SQLALCHEMY_REPOSITORIES,
        database_url: str = DATABASE_URL,
    ) -> None:
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.logger = get_logger("auth_service")
        self._repo: Any = None
        if use_sqlalchemy and SqlAuthRepository is not None:
            try:
                self._repo = SqlAuthRepository(database_url=database_url)
            except Exception:
                self._repo = None

    def get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False, timeout=5)

    def create_tables(self) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'ANALYST',
                password TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                username TEXT,
                login_time TEXT,
                expires_at TEXT
            )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS failed_logins (
                identifier TEXT PRIMARY KEY,
                failed_count INTEGER NOT NULL,
                last_failed_at TEXT NOT NULL,
                locked_until TEXT
            )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS auth_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                identifier TEXT,
                success INTEGER NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL
            )""")
        conn.commit()
        conn.close()

    def migrate_sessions_table(self) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [col[1] for col in cursor.fetchall()]
        if columns and "expires_at" not in columns:
            cursor.execute("ALTER TABLE sessions ADD COLUMN expires_at TEXT")
            conn.commit()
        conn.close()

    def migrate_users_table(self) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if "email" not in columns and columns:
            cursor.execute("ALTER TABLE users RENAME TO users_old")
            cursor.execute("""CREATE TABLE users (
                    username TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'ANALYST',
                    password TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )""")
            cursor.execute(
                "INSERT INTO users (username, email, first_name, last_name, role, password, created_at) "
                'SELECT username, "", "", "", "ANALYST", password, created_at FROM users_old'
            )
            cursor.execute("DROP TABLE users_old")
            conn.commit()
        conn.close()

    def migrate_users_role_column(self) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if columns:
            if "role" not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'ANALYST'")
                conn.commit()
            cursor.execute("UPDATE users SET role='ANALYST' WHERE role IS NULL OR TRIM(role)=''")
            conn.commit()
        conn.close()

    def initialize(self) -> None:
        if self._repo is not None:
            self.bootstrap_user_from_env()
            self.cleanup_expired_sessions()
            return
        if os.path.exists(self.db_path):
            self.migrate_users_table()
            self.migrate_users_role_column()
            self.migrate_sessions_table()
        self.create_tables()
        self.bootstrap_user_from_env()
        self.cleanup_expired_sessions()

    def bootstrap_user_from_env(self) -> None:
        email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
        username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
        first_name = os.getenv("BOOTSTRAP_ADMIN_FIRST_NAME", "Tomas").strip() or "Tomas"
        last_name = os.getenv("BOOTSTRAP_ADMIN_LAST_NAME", "Posada").strip() or "Posada"
        role = os.getenv("BOOTSTRAP_ADMIN_ROLE", "ADMIN").strip().upper() or "ADMIN"

        if not email or not password:
            return

        if not username:
            username = email.split("@", 1)[0]

        if not self.is_strong_password(password):
            self.logger.warning("bootstrap_user_skipped reason=weak_password email=%s", email)
            return

        role_clean = role if role in ALLOWED_ROLES else "ADMIN"
        if self._repo is not None:
            try:
                self._repo.upsert_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    role=role_clean,
                    password=self.hash_password(password),
                    created_at=self._utcnow(),
                )
                self.logger.info("bootstrap_user_upserted username=%s email=%s", username, email)
            except Exception as exc:
                self.logger.exception("bootstrap_user_failed email=%s error=%s", email, str(exc))
            return

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username FROM users WHERE username=? OR lower(email)=lower(?)",
                (username, email),
            )
            row = cursor.fetchone()
            hashed_password = self.hash_password(password)
            if row and row[0]:
                target_username = str(row[0])
                cursor.execute(
                    """
                    UPDATE users
                    SET email=?, first_name=?, last_name=?, role=?, password=?
                    WHERE username=?
                    """,
                    (email, first_name, last_name, role_clean, hashed_password, target_username),
                )
                self.logger.info(
                    "bootstrap_user_updated username=%s email=%s", target_username, email
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO users (username, email, first_name, last_name, role, password, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        username,
                        email,
                        first_name,
                        last_name,
                        role_clean,
                        hashed_password,
                        self._utcnow().isoformat(),
                    ),
                )
                self.logger.info("bootstrap_user_created username=%s email=%s", username, email)
            conn.commit()
        except sqlite3.Error as exc:
            self.logger.exception("bootstrap_user_failed email=%s error=%s", email, str(exc))
        finally:
            conn.close()

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(UTC)

    def _record_audit(
        self, event_type: str, identifier: str, success: bool, message: Optional[str] = None
    ) -> None:
        if self._repo is not None:
            try:
                self._repo.create_audit(
                    event_type=event_type,
                    identifier=identifier,
                    success=success,
                    message=message or "",
                    created_at=self._utcnow(),
                )
            except Exception:
                return
            return
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO auth_audit (event_type, identifier, success, message, created_at) VALUES (?, ?, ?, ?, ?)",
                (event_type, identifier, int(success), message or "", self._utcnow().isoformat()),
            )
            conn.commit()
        except sqlite3.Error:
            # Audit logging should never block auth flows.
            return
        finally:
            if conn is not None:
                conn.close()

    def _get_lockout_remaining_minutes(self, identifier: str) -> int:
        if self._repo is not None:
            locked_until_raw = self._repo.get_locked_until(identifier)
            if not locked_until_raw:
                return 0
            try:
                locked_until = datetime.fromisoformat(locked_until_raw)
            except ValueError:
                return 0
            delta = locked_until - self._utcnow()
            return max(
                0, int(delta.total_seconds() // 60) + (1 if delta.total_seconds() > 0 else 0)
            )
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT locked_until FROM failed_logins WHERE identifier=?",
                (identifier.strip().lower(),),
            )
            row = cursor.fetchone()
        finally:
            conn.close()
        if not row or not row[0]:
            return 0
        try:
            locked_until = datetime.fromisoformat(row[0])
        except ValueError:
            return 0
        delta = locked_until - self._utcnow()
        return max(0, int(delta.total_seconds() // 60) + (1 if delta.total_seconds() > 0 else 0))

    def is_locked_out(self, identifier: str) -> bool:
        return self._get_lockout_remaining_minutes(identifier) > 0

    def _register_failed_attempt(self, identifier: str) -> None:
        normalized = identifier.strip().lower()
        now = self._utcnow()
        failed_count = 0
        if self._repo is not None:
            failed_count = self._repo.get_failed_count(normalized) + 1
            locked_until_dt: datetime | None = None
            if failed_count >= MAX_FAILED_LOGIN_ATTEMPTS:
                locked_until_dt = now + timedelta(minutes=LOCKOUT_MINUTES)
            self._repo.upsert_failed_login(normalized, failed_count, now, locked_until_dt)
            self.logger.warning("failed_login identifier=%s count=%s", normalized, failed_count)
            metric(
                self.logger, "auth_failed_login", identifier=normalized, failed_count=failed_count
            )
            return
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT failed_count FROM failed_logins WHERE identifier=?",
                (normalized,),
            )
            row = cursor.fetchone()
            failed_count = (row[0] if row else 0) + 1
            locked_until_iso: str | None = None
            if failed_count >= MAX_FAILED_LOGIN_ATTEMPTS:
                locked_until_iso = (now + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
            cursor.execute(
                "INSERT OR REPLACE INTO failed_logins (identifier, failed_count, last_failed_at, locked_until) VALUES (?, ?, ?, ?)",
                (normalized, failed_count, now.isoformat(), locked_until_iso),
            )
            conn.commit()
        finally:
            conn.close()
        self.logger.warning("failed_login identifier=%s count=%s", normalized, failed_count)
        metric(self.logger, "auth_failed_login", identifier=normalized, failed_count=failed_count)

    def _clear_failed_attempts(self, identifier: str) -> None:
        if self._repo is not None:
            self._repo.clear_failed_attempts(identifier)
            return
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM failed_logins WHERE identifier=?", (identifier.strip().lower(),)
            )
            conn.commit()
        finally:
            conn.close()

    def _remaining_attempts(self, identifier: str) -> int:
        normalized = identifier.strip().lower()
        if self._repo is not None:
            failed_count = self._repo.get_failed_count(normalized)
            return int(max(0, int(MAX_FAILED_LOGIN_ATTEMPTS) - int(failed_count)))
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT failed_count FROM failed_logins WHERE identifier=?", (normalized,)
            )
            row = cursor.fetchone()
        finally:
            conn.close()
        failed_count = int(row[0]) if row and row[0] is not None else 0
        return int(max(0, int(MAX_FAILED_LOGIN_ATTEMPTS) - failed_count))

    @staticmethod
    def hash_password(password: str) -> str:
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        return bytes(hashed).decode("utf-8")

    @staticmethod
    def _legacy_hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @classmethod
    def verify_password(cls, password: str, stored_hash: str) -> bool:
        if stored_hash.startswith("$2"):
            return bool(bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")))
        return cls._legacy_hash_password(password) == stored_hash

    @staticmethod
    def is_strong_password(password: str) -> Match[str] | None:
        pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,}$"
        return re.match(pattern, password)

    @staticmethod
    def _contains_html_payload(value: str) -> bool:
        lowered = value.lower()
        return "<" in lowered or ">" in lowered or "script" in lowered

    def is_username_available(self, username: str) -> bool:
        if self._repo is not None:
            return not self._repo.username_exists(username)
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE username=?", (username.strip(),))
            result = cursor.fetchone()
        finally:
            conn.close()
        return result is None

    def is_email_available(self, email: str) -> bool:
        if self._repo is not None:
            return not self._repo.email_exists(email)
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE lower(email)=lower(?)", (email.strip(),))
            result = cursor.fetchone()
        finally:
            conn.close()
        return result is None

    def register_user(
        self,
        username: str,
        email: str,
        first_name: str,
        last_name: str,
        password: str,
        role: str = "ANALYST",
    ) -> Tuple[bool, Optional[str]]:
        username_clean = username.strip()
        email_clean = email.strip().lower()
        first_name_clean = first_name.strip()
        last_name_clean = last_name.strip()
        password_clean = password.strip()
        role_clean = role.strip().upper() if role else "ANALYST"
        if role_clean not in ALLOWED_ROLES:
            role_clean = "ANALYST"
        unsafe_fields = [username_clean, email_clean, first_name_clean, last_name_clean]
        if any(self._contains_html_payload(field) for field in unsafe_fields):
            self._record_audit(
                "register", username_clean or email_clean, False, "invalid characters"
            )
            self.logger.warning("register_rejected_html_payload identifier=%s", username_clean)
            return False, "Registration contains invalid characters."

        if self._repo is not None:
            try:
                if self._repo.username_exists(username_clean):
                    self._record_audit("register", username_clean, False, "username unavailable")
                    self.logger.info("register_failed_username username=%s", username_clean)
                    return False, "Username is not available."
                if self._repo.email_exists(email_clean):
                    self._record_audit("register", email_clean, False, "email already exists")
                    self.logger.info("register_failed_email email=%s", email_clean)
                    return False, "Email is already registered. Try logging in."
                self._repo.create_user(
                    username=username_clean,
                    email=email_clean,
                    first_name=first_name_clean,
                    last_name=last_name_clean,
                    role=role_clean,
                    password=self.hash_password(password_clean),
                    created_at=self._utcnow(),
                )
                self._record_audit("register", username_clean, True, "user registered")
                self.logger.info("register_success username=%s", username_clean)
                return True, None
            except Exception as exc:
                username_taken = self._repo.username_exists(username_clean)
                email_taken = self._repo.email_exists(email_clean)
                if username_taken:
                    self._record_audit("register", username_clean, False, "username unavailable")
                    self.logger.info("register_failed_username username=%s", username_clean)
                    return False, "Username is not available."
                if email_taken:
                    self._record_audit("register", email_clean, False, "email already exists")
                    self.logger.info("register_failed_email email=%s", email_clean)
                    return False, "Email is already registered. Try logging in."
                self._record_audit("register", username_clean, False, "data conflict")
                self.logger.exception(
                    "register_failed_data_conflict identifier=%s error=%s", username_clean, str(exc)
                )
                return False, "Registration failed due to a data conflict. Please try again."

        conn = self.get_connection()
        conn_closed = False
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM users WHERE username=?", (username_clean,))
            if cursor.fetchone():
                self._record_audit("register", username_clean, False, "username unavailable")
                self.logger.info("register_failed_username username=%s", username_clean)
                return False, "Username is not available."

            cursor.execute("SELECT 1 FROM users WHERE lower(email)=lower(?)", (email_clean,))
            if cursor.fetchone():
                self._record_audit("register", email_clean, False, "email already exists")
                self.logger.info("register_failed_email email=%s", email_clean)
                return False, "Email is already registered. Try logging in."

            cursor.execute(
                "INSERT INTO users (username, email, first_name, last_name, role, password, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    username_clean,
                    email_clean,
                    first_name_clean,
                    last_name_clean,
                    role_clean,
                    self.hash_password(password_clean),
                    self._utcnow().isoformat(),
                ),
            )
            conn.commit()
            conn.close()
            conn_closed = True
            self._record_audit("register", username_clean, True, "user registered")
            self.logger.info("register_success username=%s", username_clean)
            return True, None
        except sqlite3.IntegrityError as exc:
            rollback = getattr(conn, "rollback", None)
            if callable(rollback):
                rollback()
            # Re-check both keys to return an accurate conflict message.
            username_taken = False
            email_taken = False
            try:
                cursor.execute("SELECT 1 FROM users WHERE username=?", (username_clean,))
                username_taken = cursor.fetchone() is not None
                cursor.execute("SELECT 1 FROM users WHERE lower(email)=lower(?)", (email_clean,))
                email_taken = cursor.fetchone() is not None
            except sqlite3.Error:
                username_taken = False
                email_taken = False

            conn.close()
            conn_closed = True
            if username_taken:
                self._record_audit("register", username_clean, False, "username unavailable")
                self.logger.info("register_failed_username username=%s", username_clean)
                return False, "Username is not available."
            if email_taken:
                self._record_audit("register", email_clean, False, "email already exists")
                self.logger.info("register_failed_email email=%s", email_clean)
                return False, "Email is already registered. Try logging in."
            self._record_audit("register", username_clean, False, "data conflict")
            self.logger.exception(
                "register_failed_data_conflict identifier=%s error=%s", username_clean, str(exc)
            )
            return False, "Registration failed due to a data conflict. Please try again."
        finally:
            if not conn_closed:
                conn.close()

    def authenticate_user_with_reason(self, user_or_email: str, password: str) -> Tuple[bool, str]:
        identifier = user_or_email.strip()
        if self.is_locked_out(identifier):
            remaining = self._get_lockout_remaining_minutes(identifier)
            self._record_audit("login", identifier, False, "account locked")
            self.logger.warning("login_locked identifier=%s remaining=%s", identifier, remaining)
            return False, f"Too many failed attempts. Try again in {remaining} minute(s)."

        password_ok = False
        if self._repo is not None:
            stored_hash = self._repo.get_password_by_identifier(identifier)
            if not stored_hash:
                self._register_failed_attempt(identifier)
                self._record_audit("login", identifier, False, "unknown identifier")
                self.logger.warning("login_unknown_identifier identifier=%s", identifier)
                return False, "Invalid username/email or password."
            password_to_verify = password
            password_ok = self.verify_password(password_to_verify, stored_hash)
            if not password_ok:
                stripped_password = password.strip()
                if stripped_password != password:
                    password_ok = self.verify_password(stripped_password, stored_hash)
                    if password_ok:
                        password_to_verify = stripped_password
            if password_ok and not stored_hash.startswith("$2"):
                self._repo.upgrade_password_for_identifier(
                    identifier, self.hash_password(password_to_verify)
                )
        else:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT password FROM users WHERE username=? OR lower(email)=lower(?)",
                    (identifier, identifier),
                )
                row = cursor.fetchone()
                if not row:
                    self._register_failed_attempt(identifier)
                    self._record_audit("login", identifier, False, "unknown identifier")
                    self.logger.warning("login_unknown_identifier identifier=%s", identifier)
                    return False, "Invalid username/email or password."

                stored_hash = row[0]
                password_to_verify = password
                password_ok = self.verify_password(password_to_verify, stored_hash)
                if not password_ok:
                    stripped_password = password.strip()
                    if stripped_password != password:
                        # Accept accidental surrounding whitespace from browser autofill/copy-paste.
                        password_ok = self.verify_password(stripped_password, stored_hash)
                        if password_ok:
                            password_to_verify = stripped_password

                if password_ok and not stored_hash.startswith("$2"):
                    cursor.execute(
                        "UPDATE users SET password=? WHERE username=? OR lower(email)=lower(?)",
                        (self.hash_password(password_to_verify), identifier, identifier),
                    )
                    conn.commit()

        if not password_ok:
            self._register_failed_attempt(identifier)
            if self.is_locked_out(identifier):
                self._record_audit("login", identifier, False, "lockout threshold reached")
                self.logger.warning("login_lockout_threshold identifier=%s", identifier)
                metric(self.logger, "auth_lockout", identifier=identifier)
                return False, f"Too many failed attempts. Try again in {LOCKOUT_MINUTES} minute(s)."
            self._record_audit("login", identifier, False, "invalid password")
            self.logger.warning("login_invalid_password identifier=%s", identifier)
            remaining = self._remaining_attempts(identifier)
            return (
                False,
                f"Invalid username/email or password. Remaining attempts before lockout: {remaining}.",
            )

        self._clear_failed_attempts(identifier)
        self._record_audit("login", identifier, True, "login successful")
        self.logger.info("login_success identifier=%s", identifier)
        return True, ""

    def authenticate_user(self, user_or_email: str, password: str) -> bool:
        ok, _ = self.authenticate_user_with_reason(user_or_email, password)
        return ok

    def get_username_by_identifier(self, user_or_email: str) -> Optional[str]:
        identifier = user_or_email.strip()
        if self._repo is not None:
            return cast(Optional[str], self._repo.get_username_by_identifier(identifier))
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username FROM users WHERE username=? OR lower(email)=lower(?)",
                (identifier, identifier),
            )
            row = cursor.fetchone()
        finally:
            conn.close()
        return row[0] if row else None

    def get_user_role(self, username: str) -> str:
        if self._repo is not None:
            role = (self._repo.get_user_role(username) or "ANALYST").upper()
            return role if role in ALLOWED_ROLES else "ANALYST"
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT role FROM users WHERE username=?", (username.strip(),))
            row = cursor.fetchone()
        finally:
            conn.close()
        role = (row[0] if row and row[0] else "ANALYST").upper()
        return role if role in ALLOWED_ROLES else "ANALYST"

    def set_user_role(self, username: str, role: str) -> bool:
        role_clean = role.strip().upper()
        if role_clean not in ALLOWED_ROLES:
            return False
        if self._repo is not None:
            updated = bool(self._repo.set_user_role(username.strip(), role_clean))
            if updated:
                self._record_audit("role_update", username, True, f"role={role_clean}")
            return updated
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET role=? WHERE username=?", (role_clean, username.strip())
            )
            updated_count = cursor.rowcount if cursor.rowcount is not None else 0
            conn.commit()
        if updated_count:
            self._record_audit("role_update", username, True, f"role={role_clean}")
        return updated_count > 0

    def list_users(self) -> list[tuple[str, str, str]]:
        if self._repo is not None:
            return cast(list[tuple[str, str, str]], self._repo.list_users())
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, email, role FROM users ORDER BY username ASC")
            rows = cursor.fetchall()
        return [(str(r[0]), str(r[1]), str(r[2]).upper()) for r in rows]

    def can_access_module(self, username: str, module_name: str) -> bool:
        role = self.get_user_role(username)
        return module_name in MODULE_ACCESS_POLICY.get(role, set())

    @staticmethod
    def modules_for_role(role: str) -> list[str]:
        role_clean = role.strip().upper() if role else "ANALYST"
        allowed = MODULE_ACCESS_POLICY.get(role_clean, MODULE_ACCESS_POLICY["ANALYST"])
        return sorted(allowed)

    def create_session(
        self,
        username: str,
        ttl_minutes: int = SESSION_TTL_MINUTES,
        invalidate_existing: bool = True,
    ) -> str:
        session_id = secrets.token_hex(32)
        now = self._utcnow()
        expires_at = (now + timedelta(minutes=ttl_minutes)).isoformat()
        if self._repo is not None:
            self._repo.create_session(
                session_id=session_id,
                username=username,
                login_time=now,
                expires_at=datetime.fromisoformat(expires_at),
                invalidate_existing=invalidate_existing,
            )
            self._record_audit("session_create", username, True, "session created")
            self.logger.info("session_create username=%s", username)
            return session_id
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if invalidate_existing:
                cursor.execute("DELETE FROM sessions WHERE username=?", (username,))
            cursor.execute(
                "INSERT INTO sessions (session_id, username, login_time, expires_at) VALUES (?, ?, ?, ?)",
                (session_id, username, now.isoformat(), expires_at),
            )
            conn.commit()
        self._record_audit("session_create", username, True, "session created")
        self.logger.info("session_create username=%s", username)
        return session_id

    def is_session_valid(self, session_id: str) -> bool:
        if self._repo is not None:
            expires_at_raw = self._repo.get_session_expires_at(session_id)
            if not expires_at_raw:
                return False
            try:
                expires_at = datetime.fromisoformat(expires_at_raw)
            except ValueError:
                return False
            return expires_at > self._utcnow()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT expires_at FROM sessions WHERE session_id=?", (session_id,))
            row = cursor.fetchone()
        if not row or not row[0]:
            return False
        try:
            expires_at = datetime.fromisoformat(row[0])
        except ValueError:
            return False
        return expires_at > self._utcnow()

    def get_session_username(self, session_id: str) -> Optional[str]:
        if self._repo is not None:
            username, expires_at_raw = cast(
                tuple[Optional[str], Optional[str]],
                self._repo.get_session_username_and_expiry(session_id),
            )
            if not username or not expires_at_raw:
                return None
            try:
                expires_at = datetime.fromisoformat(expires_at_raw)
            except ValueError:
                return None
            if expires_at <= self._utcnow():
                return None
            return username
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username, expires_at FROM sessions WHERE session_id=?",
                (session_id,),
            )
            row = cursor.fetchone()
        if not row:
            return None
        username = str(row[0]) if row[0] else ""
        expires_at_raw = str(row[1]) if row[1] else ""
        if not username or not expires_at_raw:
            return None
        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
        except ValueError:
            return None
        if expires_at <= self._utcnow():
            return None
        return username

    def validate_session_owner(self, session_id: str, username: str) -> bool:
        if not session_id.strip() or not username.strip():
            return False
        session_username = self.get_session_username(session_id.strip())
        return session_username == username.strip()

    def invalidate_session(self, session_id: str) -> None:
        if self._repo is not None:
            self._repo.invalidate_session(session_id)
            self._record_audit("session_invalidate", session_id, True, "session invalidated")
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
            conn.commit()
        self._record_audit("session_invalidate", session_id, True, "session invalidated")

    def cleanup_expired_sessions(self) -> int:
        now = self._utcnow().isoformat()
        if self._repo is not None:
            deleted = int(self._repo.cleanup_expired_sessions(self._utcnow()))
            if deleted:
                self.logger.info("session_cleanup deleted=%s", deleted)
            return deleted
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM sessions WHERE expires_at IS NOT NULL AND expires_at <= ?", (now,)
            )
            deleted = cursor.rowcount if cursor.rowcount is not None else 0
            conn.commit()
        if deleted:
            self.logger.info("session_cleanup deleted=%s", deleted)
        return deleted
