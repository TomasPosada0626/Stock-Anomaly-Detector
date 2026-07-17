from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Any, Final

try:
    from cryptography.fernet import Fernet as _FernetClass
except Exception:  # pragma: no cover - optional dependency
    _FernetClass = None

Fernet: Any = _FernetClass

_PREFIX: Final[str] = "qv_enc_v1:"
_PREFIX_V2: Final[str] = "qv_enc_v2:"


def _derive_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


def _stream_cipher(payload: bytes, key_material: bytes) -> bytes:
    output = bytearray(len(payload))
    for idx, byte in enumerate(payload):
        output[idx] = byte ^ key_material[idx % len(key_material)]
    return bytes(output)


def encrypt_value(value: str, secret: str) -> str:
    if not secret:
        raise ValueError("secret is required")
    payload = value.encode("utf-8")
    key = _derive_key(secret)
    nonce = secrets.token_bytes(16)
    stream_key = hashlib.sha256(key + nonce).digest()
    encrypted = _stream_cipher(payload, stream_key)
    signature = hmac.new(key, nonce + encrypted, hashlib.sha256).digest()
    token = nonce + encrypted + signature
    return _PREFIX_V2 + base64.urlsafe_b64encode(token).decode("ascii")


def _decrypt_v1(token: str, secret: str) -> str:
    raw = base64.urlsafe_b64decode(token[len(_PREFIX) :].encode("ascii"))
    key = _derive_key(secret)
    decrypted = _stream_cipher(raw, key)
    return decrypted.decode("utf-8")


def _decrypt_v2(token: str, secret: str) -> str:
    raw = base64.urlsafe_b64decode(token[len(_PREFIX_V2) :].encode("ascii"))
    if len(raw) < 48:
        raise ValueError("invalid token payload")
    nonce = raw[:16]
    encrypted = raw[16:-32]
    given_signature = raw[-32:]
    key = _derive_key(secret)
    expected_signature = hmac.new(key, nonce + encrypted, hashlib.sha256).digest()
    if not hmac.compare_digest(given_signature, expected_signature):
        raise ValueError("invalid token signature")
    stream_key = hashlib.sha256(key + nonce).digest()
    decrypted = _stream_cipher(encrypted, stream_key)
    return decrypted.decode("utf-8")


def decrypt_value(token: str, secret: str) -> str:
    if token.startswith(_PREFIX_V2):
        return _decrypt_v2(token, secret)
    if token.startswith(_PREFIX):
        return _decrypt_v1(token, secret)
    raise ValueError("invalid token format")


def encrypt_data(data: str, key: str) -> str:
    """Encrypt data at rest using Fernet-compatible keys."""
    if Fernet is None:
        # Fallback keeps compatibility in environments without cryptography.
        return encrypt_value(data, key)
    f = Fernet(key.encode("utf-8"))
    encrypted_bytes = bytes(f.encrypt(data.encode("utf-8")))
    return encrypted_bytes.decode("utf-8")


def decrypt_data(encrypted: str, key: str) -> str:
    """Decrypt data at rest using Fernet-compatible keys."""
    if Fernet is None:
        return decrypt_value(encrypted, key)
    f = Fernet(key.encode("utf-8"))
    decrypted_bytes = bytes(f.decrypt(encrypted.encode("utf-8")))
    return decrypted_bytes.decode("utf-8")
