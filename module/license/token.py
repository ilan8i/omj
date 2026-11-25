# This Python file uses the following encoding: utf-8
"""授权令牌校验。

令牌格式：base64url(payload) + "." + base64url(signature)
payload 为 JSON，签名为 Ed25519 对 payload 原文的签名。
"""
import base64
import hmac
import json
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from module.license import constants
from module.license.errors import (
    CLOCK_ROLLBACK,
    LICENSE_EXPIRED,
    MACHINE_MISMATCH,
    TOKEN_EXPIRED,
    TOKEN_INVALID,
    LicenseError,
)
from module.license.machine import machine_fingerprint


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def verify_token(token: str, machine_code: str, check_expiry: bool = True) -> dict:
    """校验令牌并返回 claims。

    check_expiry=False 时只校验签名和机器指纹，用于读取已过期令牌里的
    license_exp，判断是否仍在离线宽限期内。
    """
    if not isinstance(token, str) or token.count(".") != 1:
        raise LicenseError(TOKEN_INVALID, "授权令牌格式错误")

    payload_b64, signature_b64 = token.split(".", 1)
    try:
        payload = _b64decode(payload_b64)
        signature = _b64decode(signature_b64)
        claims = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise LicenseError(TOKEN_INVALID, "授权令牌格式错误") from exc

    if not isinstance(claims, dict):
        raise LicenseError(TOKEN_INVALID, "授权令牌内容错误")

    public_key = constants.get_public_key_bytes()
    if len(public_key) != 32:
        raise LicenseError(TOKEN_INVALID, "授权公钥未配置")

    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, payload)
    except InvalidSignature as exc:
        raise LicenseError(TOKEN_INVALID, "授权令牌签名无效") from exc
    except Exception as exc:
        raise LicenseError(TOKEN_INVALID, "授权令牌签名无效") from exc

    expected_machine = machine_fingerprint(machine_code)
    actual_machine = str(claims.get("mch") or "").lower()
    if not expected_machine or not hmac.compare_digest(actual_machine, expected_machine):
        raise LicenseError(MACHINE_MISMATCH, "授权令牌与当前设备不匹配")

    now = int(time.time())
    try:
        issued_at = int(claims.get("iat") or 0)
        token_exp = int(claims.get("tok_exp") or 0)
        license_exp = int(claims.get("lic_exp") or 0)
    except (TypeError, ValueError) as exc:
        raise LicenseError(TOKEN_INVALID, "授权令牌时间字段错误") from exc

    if issued_at > now + 300:
        raise LicenseError(CLOCK_ROLLBACK, "本机时间异常，请校准系统时间")

    if check_expiry:
        if license_exp and license_exp <= now:
            raise LicenseError(LICENSE_EXPIRED, "授权已过期")
        if token_exp and token_exp <= now:
            raise LicenseError(TOKEN_EXPIRED, "授权令牌已过期，需要联网刷新")

    return claims
