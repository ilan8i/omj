import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from module.license import constants, token
from module.license.errors import (
    CLOCK_ROLLBACK,
    LICENSE_EXPIRED,
    MACHINE_MISMATCH,
    TOKEN_EXPIRED,
    TOKEN_INVALID,
    LicenseError,
)
from module.license.machine import machine_fingerprint

MACHINE_CODE = "sha256:" + "a" * 64


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _sign(claims: dict, private_key: Ed25519PrivateKey) -> str:
    payload = json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = private_key.sign(payload)
    return f"{_b64(payload)}.{_b64(signature)}"


@pytest.fixture()
def signing_key(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    public_raw = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    monkeypatch.setattr(constants, "get_public_key_bytes", lambda: public_raw)
    return private_key


def _claims(**overrides):
    now = int(time.time())
    claims = {
        "sub": "lic-1",
        "mch": machine_fingerprint(MACHINE_CODE),
        "plan": "month_30d",
        "lic_exp": now + 86400,
        "tok_exp": now + 3600,
        "iat": now,
        "jti": "jti-1",
    }
    claims.update(overrides)
    return claims


def test_valid_token(signing_key):
    claims = token.verify_token(_sign(_claims(), signing_key), MACHINE_CODE)
    assert claims["sub"] == "lic-1"
    assert claims["plan"] == "month_30d"


def test_tampered_payload(signing_key):
    value = _sign(_claims(), signing_key)
    payload, signature = value.split(".", 1)
    tampered = _b64(b'{"sub":"hacked"}')
    with pytest.raises(LicenseError) as exc:
        token.verify_token(f"{tampered}.{signature}", MACHINE_CODE)
    assert exc.value.code == TOKEN_INVALID


def test_bad_signature(signing_key):
    other_key = Ed25519PrivateKey.generate()
    value = _sign(_claims(), other_key)
    with pytest.raises(LicenseError) as exc:
        token.verify_token(value, MACHINE_CODE)
    assert exc.value.code == TOKEN_INVALID


def test_expired_token(signing_key):
    now = int(time.time())
    value = _sign(_claims(tok_exp=now - 1, lic_exp=now + 3600), signing_key)
    with pytest.raises(LicenseError) as exc:
        token.verify_token(value, MACHINE_CODE)
    assert exc.value.code == TOKEN_EXPIRED


def test_expired_license(signing_key):
    now = int(time.time())
    value = _sign(_claims(tok_exp=now + 3600, lic_exp=now - 1), signing_key)
    with pytest.raises(LicenseError) as exc:
        token.verify_token(value, MACHINE_CODE)
    assert exc.value.code == LICENSE_EXPIRED


def test_machine_mismatch(signing_key):
    value = _sign(_claims(mch="b" * 16), signing_key)
    with pytest.raises(LicenseError) as exc:
        token.verify_token(value, MACHINE_CODE)
    assert exc.value.code == MACHINE_MISMATCH


def test_clock_rollback(signing_key):
    now = int(time.time())
    value = _sign(_claims(iat=now + 3600), signing_key)
    with pytest.raises(LicenseError) as exc:
        token.verify_token(value, MACHINE_CODE)
    assert exc.value.code == CLOCK_ROLLBACK
