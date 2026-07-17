from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = ModuleType("streamlit")

import ui.auth_ui as auth_ui


class _DummyCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyStatus:
    def error(self, *_args, **_kwargs):
        return None

    def success(self, *_args, **_kwargs):
        return None


class _FakeStreamlit:
    def __init__(self, option: str, inputs: dict[str, str], click_label: str):
        self.query_params = {}
        self.session_state = {}
        self._option = option
        self._inputs = inputs
        self._click_label = click_label

    def markdown(self, *_args, **_kwargs):
        return None

    def columns(self, _spec):
        return (_DummyCtx(), _DummyCtx(), _DummyCtx())

    def radio(self, _label, _options, horizontal=False, key=None):
        if key:
            self.session_state[key] = self._option
        return self._option

    def subheader(self, *_args, **_kwargs):
        return None

    def caption(self, *_args, **_kwargs):
        return None

    def text_input(self, label: str, value: str = "", type: str | None = None):  # noqa: A002
        _ = type
        return self._inputs.get(label, value)

    def empty(self):
        return _DummyStatus()

    def checkbox(self, *_args, **_kwargs):
        return False

    def button(self, label: str):
        return label == self._click_label

    def success(self, *_args, **_kwargs):
        return None

    def error(self, *_args, **_kwargs):
        return None

    def info(self, *_args, **_kwargs):
        return None

    def rerun(self):
        return None


def test_get_and_set_remembered_identifier() -> None:
    fake_st = _FakeStreamlit(option="Login", inputs={}, click_label="")
    auth_ui.st = fake_st

    auth_ui._set_remembered_identifier("alice@example.com")
    assert auth_ui._get_remembered_identifier() == "alice@example.com"

    auth_ui._set_remembered_identifier("")
    assert auth_ui._get_remembered_identifier() == ""


def test_render_login_panel_login_success_sets_session_state(monkeypatch) -> None:
    fake_st = _FakeStreamlit(
        option="Login",
        inputs={
            "Username or Email": "alice",
            "Password": "Strong*Pass1",
        },
        click_label="Login",
    )
    auth_ui.st = fake_st

    auth_service = SimpleNamespace(
        authenticate_user_with_reason=lambda identifier, password: (True, ""),
        get_username_by_identifier=lambda identifier: "alice",
        create_session=lambda username: "session-123",
        get_user_role=lambda username: "ANALYST",
    )

    auth_ui.render_login_panel(auth_service)

    assert fake_st.session_state["logged_in"] is True
    assert fake_st.session_state["username"] == "alice"
    assert fake_st.session_state["session_id"] == "session-123"
    assert fake_st.session_state["role"] == "ANALYST"


def test_render_login_panel_register_rejects_weak_password() -> None:
    fake_st = _FakeStreamlit(
        option="Register",
        inputs={
            "First Name": "A",
            "Last Name": "B",
            "Username": "alice",
            "Email": "alice@example.com",
            "Password": "weak",
            "Repeat Password": "weak",
        },
        click_label="Register",
    )
    auth_ui.st = fake_st

    auth_service = SimpleNamespace(
        is_username_available=lambda username: True,
        is_email_available=lambda email: True,
        is_strong_password=lambda pwd: False,
        register_user=lambda *args, **kwargs: (False, "should not be called"),
    )

    auth_ui.render_login_panel(auth_service)
    assert fake_st.session_state.get("logged_in", False) is False
