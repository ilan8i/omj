# This Python file uses the following encoding: utf-8
"""授权服务 HTTP 客户端。

本模块不记录任何密钥或令牌内容。
"""
import sys

import requests

from module.license import constants
from module.license.errors import (
    INVALID_KEY,
    INSECURE_SERVER,
    LICENSE_EXPIRED,
    LICENSE_REVOKED,
    MACHINE_MISMATCH,
    NETWORK_ERROR,
    RATE_LIMITED,
    SERVER_ERROR,
    TOKEN_EXPIRED,
    TOKEN_INVALID,
    LicenseError,
)

_ERROR_BY_STATUS = {
    400: INVALID_KEY,
    401: TOKEN_EXPIRED,
    403: LICENSE_REVOKED,
    409: MACHINE_MISMATCH,
    410: LICENSE_EXPIRED,
    429: RATE_LIMITED,
}
_SERVER_DENIED_STATUS = {400, 403, 409, 410}


def _post(server: str, path: str, payload: dict) -> dict:
    server = (server or "").strip().rstrip("/")
    if not server.startswith("https://") and not constants.is_dev():
        raise LicenseError(INSECURE_SERVER, "授权服务必须使用 HTTPS")

    url = server + path
    try:
        response = requests.post(url, json=payload, timeout=(5, 10))
    except requests.exceptions.RequestException as exc:
        raise LicenseError(
            NETWORK_ERROR, f"无法连接授权服务: {exc.__class__.__name__}"
        ) from exc

    try:
        body = response.json()
    except ValueError:
        body = {}

    if 200 <= response.status_code < 300:
        if not isinstance(body, dict):
            raise LicenseError(SERVER_ERROR, "授权服务返回格式错误")
        return body

    code = _ERROR_BY_STATUS.get(response.status_code, SERVER_ERROR)
    if isinstance(body, dict) and body.get("code") in {
        INVALID_KEY,
        LICENSE_REVOKED,
        MACHINE_MISMATCH,
        LICENSE_EXPIRED,
        RATE_LIMITED,
        SERVER_ERROR,
        TOKEN_EXPIRED,
        TOKEN_INVALID,
    }:
        code = str(body["code"])

    message = ""
    if isinstance(body, dict):
        message = str(body.get("message") or "")
    if not message:
        message = f"授权服务返回 {response.status_code}"

    raise LicenseError(
        code,
        message,
        server_denied=response.status_code in _SERVER_DENIED_STATUS,
    )


def activate(server: str, key: str, machine: str, app_version: str) -> dict:
    return _post(
        server,
        "/v1/activate",
        {
            "key": key,
            "machine": machine,
            "app_version": app_version,
            "os": "windows" if sys.platform.startswith("win") else sys.platform,
        },
    )


def heartbeat(server: str, token: str, machine: str, app_version: str) -> dict:
    return _post(
        server,
        "/v1/heartbeat",
        {
            "token": token,
            "machine": machine,
            "app_version": app_version,
        },
    )
