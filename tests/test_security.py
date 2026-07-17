from __future__ import annotations

from pathlib import Path

from security.csrf import generate_csrf_token, verify_csrf_token
from services.auth_service import AuthService


def test_sql_injection_prevention(tmp_path: Path) -> None:
    auth_service = AuthService(str(tmp_path / "users.db"))
    auth_service.initialize()

    injection = "' OR '1'='1"
    ok, _ = auth_service.authenticate_user_with_reason(injection, "password")
    assert ok is False
    assert auth_service.list_users() == []


def test_xss_prevention(tmp_path: Path) -> None:
    auth_service = AuthService(str(tmp_path / "users.db"))
    auth_service.initialize()

    payload = '<script>alert("xss")</script>'
    success, msg = auth_service.register_user(
        username=payload,
        email="test@test.com",
        first_name="Test",
        last_name="User",
        password="Pass123!@",
    )

    assert success is False
    assert msg is not None
    assert "invalid" in msg.lower()


def test_brute_force_protection(tmp_path: Path) -> None:
    auth_service = AuthService(str(tmp_path / "users.db"))
    auth_service.initialize()
    ok, err = auth_service.register_user(
        "testuser",
        "test@test.com",
        "Test",
        "User",
        "Pass123!@",
    )
    assert ok is True
    assert err is None

    for _ in range(5):
        auth_service.authenticate_user_with_reason("testuser", "wrongpassword")

    success, msg = auth_service.authenticate_user_with_reason("testuser", "Pass123!@")
    assert success is False
    assert "too many" in msg.lower() or "lock" in msg.lower()


def test_session_hijacking_prevention(tmp_path: Path) -> None:
    auth_service = AuthService(str(tmp_path / "users.db"))
    auth_service.initialize()
    ok, _ = auth_service.register_user(
        "user1",
        "user1@test.com",
        "User",
        "One",
        "Pass123!@",
    )
    assert ok is True

    session1 = auth_service.create_session("user1")
    session2 = auth_service.create_session("user1")

    assert session1 != session2
    assert len(session1) > 60
    assert len(session2) > 60


def test_csrf_token_generation_and_validation() -> None:
    token = generate_csrf_token()
    session_store = {"csrf_token": token}

    assert len(token) == 64
    assert verify_csrf_token(token, session_store) is True
    assert verify_csrf_token("bad-token", session_store) is False
