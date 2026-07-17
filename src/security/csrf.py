from __future__ import annotations

import secrets
from collections.abc import MutableMapping


def generate_csrf_token() -> str:
    """Generate CSRF token for forms."""
    return secrets.token_hex(32)


def verify_csrf_token(token: str, session_store: MutableMapping[str, object]) -> bool:
    """Verify CSRF token validity against session storage."""
    expected = str(session_store.get("csrf_token", ""))
    return bool(token) and token == expected
