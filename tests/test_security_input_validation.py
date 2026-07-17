import pandas as pd
import pytest

from security.encryption import decrypt_value, encrypt_value
from security.input_validation import (
    require_ticker_whitelist,
    sanitize_csv_upload,
    sanitize_ticker,
)


def test_sanitize_ticker_accepts_valid_symbol() -> None:
    assert sanitize_ticker(" aapl ") == "AAPL"


def test_sanitize_ticker_rejects_invalid_symbol() -> None:
    with pytest.raises(ValueError, match="invalid ticker"):
        sanitize_ticker("AAPL;DROP TABLE")


def test_require_ticker_whitelist_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="ticker not allowed"):
        require_ticker_whitelist("SPY", {"AAPL", "MSFT"})


def test_sanitize_csv_upload_parses_valid_data() -> None:
    csv = "Date,Close\n2026-01-01,100\n2026-01-02,101\n"
    frame = sanitize_csv_upload(csv)
    assert isinstance(frame, pd.DataFrame)
    assert len(frame) == 2


def test_sanitize_csv_upload_rejects_suspicious_columns() -> None:
    csv = "script,Close\nalert(1),100\n"
    with pytest.raises(ValueError, match="suspicious"):
        sanitize_csv_upload(csv)


def test_encrypt_decrypt_roundtrip() -> None:
    secret = "quantvision-test-secret"
    token = encrypt_value("sensitive_value", secret)
    assert token.startswith("qv_enc_v")
    assert decrypt_value(token, secret) == "sensitive_value"


def test_encrypt_rejects_tampered_token() -> None:
    secret = "quantvision-test-secret"
    token = encrypt_value("sensitive_value", secret)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(ValueError):
        decrypt_value(tampered, secret)
