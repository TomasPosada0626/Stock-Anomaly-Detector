import hashlib
import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from services.auth_service import AuthService


def test_register_and_authenticate_success(tmp_path) -> None:
    db_path = tmp_path / "test_users.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    ok, err = auth.register_user("tomas1", "tomas1@email.com", "Tomas", "Posada", "Strong*Pass1")
    assert ok is True
    assert err is None
    assert auth.authenticate_user("tomas1", "Strong*Pass1") is True


def test_duplicate_email_is_rejected(tmp_path) -> None:
    db_path = tmp_path / "test_users.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    auth.register_user("userA", "same@email.com", "A", "A", "Strong*Pass1")
    ok, err = auth.register_user("userB", "same@email.com", "B", "B", "Strong*Pass1")

    assert ok is False
    assert err == "Email is already registered. Try logging in."


def test_duplicate_username_is_rejected(tmp_path) -> None:
    db_path = tmp_path / "test_users.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    auth.register_user("sameuser", "a@email.com", "A", "A", "Strong*Pass1")
    ok, err = auth.register_user("sameuser", "b@email.com", "B", "B", "Strong*Pass1")

    assert ok is False
    assert err == "Username is not available."


def test_login_with_email_works(tmp_path) -> None:
    db_path = tmp_path / "test_users.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    auth.register_user("mailuser", "mailuser@email.com", "M", "U", "Strong*Pass1")
    assert auth.authenticate_user("mailuser@email.com", "Strong*Pass1") is True


def test_register_trims_password_and_login_with_trimmed_password(tmp_path) -> None:
    db_path = tmp_path / "trimmed_register.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    ok, err = auth.register_user("trimuser", "trim@email.com", "T", "U", "  Strong*Pass1  ")
    assert ok is True
    assert err is None

    assert auth.authenticate_user("trimuser", "Strong*Pass1") is True


def test_login_accepts_password_with_surrounding_whitespace(tmp_path) -> None:
    db_path = tmp_path / "trimmed_login.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    auth.register_user("spaceuser", "space@email.com", "S", "U", "Strong*Pass1")
    assert auth.authenticate_user("spaceuser", "   Strong*Pass1   ") is True


def test_session_creation_persists_row(tmp_path) -> None:
    db_path = tmp_path / "test_users.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    auth.register_user("sessuser", "sess@email.com", "S", "U", "Strong*Pass1")
    session_id = auth.create_session("sessuser")

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT username FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "sessuser"


def test_username_and_email_availability_checks(tmp_path) -> None:
    db_path = tmp_path / "test_users.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    assert auth.is_username_available("newuser") is True
    assert auth.is_email_available("new@email.com") is True

    auth.register_user("newuser", "new@email.com", "N", "U", "Strong*Pass1")

    assert auth.is_username_available("newuser") is False
    assert auth.is_email_available("NEW@email.com") is False


def test_get_username_by_identifier_for_username_and_email(tmp_path) -> None:
    db_path = tmp_path / "test_users.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    auth.register_user("lookupuser", "lookup@email.com", "L", "U", "Strong*Pass1")

    assert auth.get_username_by_identifier("lookupuser") == "lookupuser"
    assert auth.get_username_by_identifier("lookup@email.com") == "lookupuser"
    assert auth.get_username_by_identifier("missing") is None


def test_password_strength_and_hash_behavior() -> None:
    assert AuthService.is_strong_password("Strong*Pass1") is not None
    assert AuthService.is_strong_password("weakpass") is None
    hashed = AuthService.hash_password("abc")
    assert hashed.startswith("$2")
    assert AuthService.verify_password("abc", hashed) is True
    assert AuthService.verify_password("wrong", hashed) is False


def test_initialize_migrates_old_users_schema(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE users (username TEXT PRIMARY KEY, password TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
        ("legacy", "hashed", "2026-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()

    auth = AuthService(str(db_path))
    auth.initialize()

    conn = sqlite3.connect(str(db_path))
    cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    migrated = conn.execute("SELECT username, email FROM users WHERE username='legacy'").fetchone()
    conn.close()

    assert "email" in cols
    assert migrated is not None
    assert migrated[1] == ""


def test_register_user_handles_generic_integrity_error(monkeypatch, tmp_path) -> None:
    class FakeCursor:
        def execute(self, *args, **kwargs):
            raise sqlite3.IntegrityError("generic integrity error")

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    db_path = tmp_path / "test_users.db"
    auth = AuthService(str(db_path))
    monkeypatch.setattr(auth, "get_connection", lambda: FakeConnection())

    ok, err = auth.register_user("u", "e@e.com", "F", "L", "Strong*Pass1")

    assert ok is False
    assert err == "Registration failed due to a data conflict. Please try again."


def test_register_user_integrity_error_recheck_username_conflict(monkeypatch, tmp_path) -> None:
    class FakeCursor:
        def __init__(self):
            self.username_select_calls = 0
            self.email_select_calls = 0
            self.last_query = ""

        def execute(self, query, params):
            if query.startswith("SELECT 1 FROM users WHERE username"):
                self.username_select_calls += 1
                self.last_query = "username"
                return None

            if query.startswith("SELECT 1 FROM users WHERE lower(email)=lower"):
                self.email_select_calls += 1
                self.last_query = "email"
                return None

            if query.startswith("INSERT INTO users"):
                self.last_query = "insert"
                raise sqlite3.IntegrityError("forced insert conflict")

            return None

        def fetchone(self):
            if self.last_query == "username":
                if self.username_select_calls == 1:
                    return None
                return (1,)
            if self.last_query == "email":
                return None
            return None

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self):
            return self.cursor_obj

        def rollback(self):
            return None

        def close(self):
            return None

        def commit(self):
            return None

    db_path = tmp_path / "test_users.db"
    auth = AuthService(str(db_path))
    monkeypatch.setattr(auth, "get_connection", lambda: FakeConnection())

    ok, err = auth.register_user("u", "e@e.com", "F", "L", "Strong*Pass1")

    assert ok is False
    assert err == "Username is not available."


def test_register_user_integrity_error_recheck_email_conflict(monkeypatch, tmp_path) -> None:
    class FakeCursor:
        def __init__(self):
            self.username_select_calls = 0
            self.email_select_calls = 0
            self.last_query = ""

        def execute(self, query, params):
            if query.startswith("SELECT 1 FROM users WHERE username"):
                self.username_select_calls += 1
                self.last_query = "username"
                return None

            if query.startswith("SELECT 1 FROM users WHERE lower(email)=lower"):
                self.email_select_calls += 1
                self.last_query = "email"
                return None

            if query.startswith("INSERT INTO users"):
                self.last_query = "insert"
                raise sqlite3.IntegrityError("forced insert conflict")

            return None

        def fetchone(self):
            if self.last_query == "username":
                return None
            if self.last_query == "email":
                if self.email_select_calls == 1:
                    return None
                return (1,)
            return None

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self):
            return self.cursor_obj

        def rollback(self):
            return None

        def close(self):
            return None

        def commit(self):
            return None

    db_path = tmp_path / "test_users.db"
    auth = AuthService(str(db_path))
    monkeypatch.setattr(auth, "get_connection", lambda: FakeConnection())

    ok, err = auth.register_user("u", "e@e.com", "F", "L", "Strong*Pass1")

    assert ok is False
    assert err == "Email is already registered. Try logging in."


def test_authenticate_upgrades_legacy_sha256_hash(tmp_path) -> None:
    db_path = tmp_path / "legacy_auth.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    conn = sqlite3.connect(str(db_path))
    legacy_hash = hashlib.sha256("Strong*Pass1".encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT INTO users (username, email, first_name, last_name, password, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("legacyuser", "legacy@email.com", "L", "U", legacy_hash, "2026-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()

    assert auth.authenticate_user("legacyuser", "Strong*Pass1") is True

    conn = sqlite3.connect(str(db_path))
    new_hash = conn.execute("SELECT password FROM users WHERE username='legacyuser'").fetchone()[0]
    conn.close()
    assert new_hash.startswith("$2")


def test_lockout_after_multiple_failed_attempts(tmp_path) -> None:
    db_path = tmp_path / "lockout.db"
    auth = AuthService(str(db_path))
    auth.initialize()
    auth.register_user("lockeduser", "locked@email.com", "L", "U", "Strong*Pass1")

    for _ in range(5):
        ok, _ = auth.authenticate_user_with_reason("lockeduser", "wrong-password")
        assert ok is False

    ok, message = auth.authenticate_user_with_reason("lockeduser", "Strong*Pass1")
    assert ok is False
    assert "Too many failed attempts" in message


def test_invalid_login_includes_remaining_attempts_message(tmp_path) -> None:
    db_path = tmp_path / "remaining.db"
    auth = AuthService(str(db_path))
    auth.initialize()
    auth.register_user("remuser", "rem@email.com", "R", "U", "Strong*Pass1")

    ok, message = auth.authenticate_user_with_reason("remuser", "wrong-password")

    assert ok is False
    assert "Remaining attempts before lockout" in message


def test_unknown_identifier_returns_invalid_credentials_message(tmp_path) -> None:
    db_path = tmp_path / "unknown-user.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    ok, message = auth.authenticate_user_with_reason("nobody@nope.com", "Strong*Pass1")

    assert ok is False
    assert message == "Invalid username/email or password."


def test_session_validity_and_invalidation(tmp_path) -> None:
    db_path = tmp_path / "session.db"
    auth = AuthService(str(db_path))
    auth.initialize()
    auth.register_user("sesscheck", "sesscheck@email.com", "S", "C", "Strong*Pass1")

    session_id = auth.create_session("sesscheck", ttl_minutes=1)
    assert auth.is_session_valid(session_id) is True

    auth.invalidate_session(session_id)
    assert auth.is_session_valid(session_id) is False


def test_expired_session_returns_invalid(tmp_path) -> None:
    db_path = tmp_path / "expired.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO sessions (session_id, username, login_time, expires_at) VALUES (?, ?, ?, ?)",
        (
            "expired-session",
            "user",
            datetime.now(UTC).isoformat(),
            (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    assert auth.is_session_valid("expired-session") is False


def test_session_with_invalid_timestamp_returns_invalid(tmp_path) -> None:
    db_path = tmp_path / "invalid-timestamp.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO sessions (session_id, username, login_time, expires_at) VALUES (?, ?, ?, ?)",
        ("bad-session", "user", datetime.now(UTC).isoformat(), "not-a-timestamp"),
    )
    conn.commit()
    conn.close()

    assert auth.is_session_valid("bad-session") is False


def test_audit_log_records_events(tmp_path) -> None:
    db_path = tmp_path / "audit.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    auth.register_user("auduser", "aud@email.com", "A", "U", "Strong*Pass1")
    auth.authenticate_user_with_reason("auduser", "Strong*Pass1")

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT event_type, success FROM auth_audit").fetchall()
    conn.close()

    assert any(r[0] == "register" and r[1] == 1 for r in rows)
    assert any(r[0] == "login" and r[1] == 1 for r in rows)


def test_create_session_invalidates_previous_by_default(tmp_path) -> None:
    db_path = tmp_path / "single-session.db"
    auth = AuthService(str(db_path))
    auth.initialize()
    auth.register_user("solo", "solo@email.com", "S", "O", "Strong*Pass1")

    old_session = auth.create_session("solo")
    new_session = auth.create_session("solo")

    assert old_session != new_session
    assert auth.is_session_valid(old_session) is False
    assert auth.is_session_valid(new_session) is True


def test_cleanup_expired_sessions_removes_old_rows(tmp_path) -> None:
    db_path = tmp_path / "cleanup.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO sessions (session_id, username, login_time, expires_at) VALUES (?, ?, ?, ?)",
        (
            "old-session",
            "user",
            datetime.now(UTC).isoformat(),
            (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    deleted = auth.cleanup_expired_sessions()

    assert deleted >= 1
    assert auth.is_session_valid("old-session") is False

def test_user_roles_default_update_and_policy(tmp_path) -> None:
    db_path = tmp_path / "roles.db"
    auth = AuthService(str(db_path))
    auth.initialize()

    auth.register_user("analyst1", "analyst1@email.com", "A", "N", "Strong*Pass1")
    assert auth.get_user_role("analyst1") == "ANALYST"
    assert auth.can_access_module("analyst1", "Dashboard") is True
    assert auth.can_access_module("analyst1", "Admin") is False

    updated = auth.set_user_role("analyst1", "ADMIN")
    assert updated is True
    assert auth.get_user_role("analyst1") == "ADMIN"
    assert auth.can_access_module("analyst1", "Admin") is True

    assert auth.set_user_role("analyst1", "INVALID") is False
