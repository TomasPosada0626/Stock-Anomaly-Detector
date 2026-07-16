import os
import sqlite3
import sys

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
    assert AuthService.hash_password("abc") == AuthService.hash_password("abc")


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
