import time

import pytest

from module.license import constants
from module.license import service as service_mod
from module.license.errors import (
    LICENSE_REVOKED,
    NETWORK_ERROR,
    LicenseError,
)
from module.license.state import LicenseState

MACHINE_CODE = "sha256:" + "a" * 64


def _claims(token_exp: int, license_exp: int) -> dict:
    now = int(time.time())
    return {
        "sub": "lic-1",
        "mch": "a" * 16,
        "plan": "month_30d",
        "tok_exp": token_exp,
        "lic_exp": license_exp,
        "iat": now - 10,
        "jti": "jti-1",
        "perms": ["switch_account", "assist_battle"],
    }


def _response(now: int) -> dict:
    return {
        "token": "test-token",
        "token_exp": now + 3600,
        "license_exp": now + 86400,
        "plan": "month_30d",
        "server_time": now,
    }


@pytest.fixture()
def svc(monkeypatch):
    state = {"claims": _claims(int(time.time()) + 3600, int(time.time()) + 86400)}

    monkeypatch.setattr(service_mod, "get_machine_code", lambda: MACHINE_CODE)
    monkeypatch.setattr(
        service_mod, "verify_token", lambda *args, **kwargs: dict(state["claims"])
    )
    monkeypatch.setattr(service_mod.cache, "save", lambda data: None)
    monkeypatch.setattr(service_mod.cache, "clear", lambda: None)
    monkeypatch.setattr(service_mod.cache, "load", lambda: None)
    monkeypatch.setattr(
        service_mod.constants, "get_server_url", lambda: "https://license.test"
    )
    monkeypatch.setattr(
        service_mod.constants, "get_app_version", lambda: "1.0.0"
    )

    return service_mod.LicenseService(), state


def test_activate_success(svc, monkeypatch):
    license_service, state = svc
    now = int(time.time())
    monkeypatch.setattr(
        service_mod.client, "activate", lambda *args, **kwargs: _response(now)
    )
    status = license_service.activate("OAS-KEY")
    assert status.state == LicenseState.ACTIVE
    assert status.plan == "month_30d"
    assert license_service.has_permission("switch_account")
    assert license_service.has_permission("assist_battle")
    assert not license_service.has_permission("unknown")
    assert "switch_account" in status.to_dict()["permissions"]


def test_heartbeat_network_error_keeps_active(svc, monkeypatch):
    license_service, state = svc
    now = int(time.time())
    monkeypatch.setattr(
        service_mod.client, "activate", lambda *args, **kwargs: _response(now)
    )
    license_service.activate("OAS-KEY")

    def _fail(*args, **kwargs):
        raise LicenseError(NETWORK_ERROR, "offline")

    monkeypatch.setattr(service_mod.client, "heartbeat", _fail)
    status = license_service.heartbeat()
    assert status.state == LicenseState.ACTIVE


def test_heartbeat_network_error_enters_grace(svc, monkeypatch):
    license_service, state = svc
    now = int(time.time())
    monkeypatch.setattr(
        service_mod.client, "activate", lambda *args, **kwargs: _response(now)
    )
    license_service.activate("OAS-KEY")

    state["claims"] = _claims(now - 1, now + 86400)

    def _fail(*args, **kwargs):
        raise LicenseError(NETWORK_ERROR, "offline")

    monkeypatch.setattr(service_mod.client, "heartbeat", _fail)
    status = license_service.heartbeat()
    assert status.state == LicenseState.GRACE


def test_heartbeat_network_error_expires_beyond_grace(svc, monkeypatch):
    license_service, state = svc
    now = int(time.time())
    monkeypatch.setattr(
        service_mod.client, "activate", lambda *args, **kwargs: _response(now)
    )
    license_service.activate("OAS-KEY")

    state["claims"] = _claims(now - 1, now + 86400)
    license_service._last_ok_at = (
        now - constants.OFFLINE_GRACE_SECONDS - 10
    )

    def _fail(*args, **kwargs):
        raise LicenseError(NETWORK_ERROR, "offline")

    monkeypatch.setattr(service_mod.client, "heartbeat", _fail)
    status = license_service.heartbeat()
    assert status.state == LicenseState.EXPIRED


def test_heartbeat_server_revoked(svc, monkeypatch):
    license_service, state = svc
    now = int(time.time())
    monkeypatch.setattr(
        service_mod.client, "activate", lambda *args, **kwargs: _response(now)
    )
    license_service.activate("OAS-KEY")

    def _revoked(*args, **kwargs):
        raise LicenseError(LICENSE_REVOKED, "revoked", server_denied=True)

    monkeypatch.setattr(service_mod.client, "heartbeat", _revoked)
    status = license_service.heartbeat()
    assert status.state == LicenseState.REVOKED


def test_clock_rollback(svc):
    license_service, state = svc
    now = int(time.time())
    license_service._token = "test-token"
    license_service._last_server_time = now + 3600
    status = license_service.refresh_local()
    assert status.state == LicenseState.CLOCK_ROLLBACK


def test_deactivate_clears_permissions(svc, monkeypatch):
    license_service, state = svc
    now = int(time.time())
    monkeypatch.setattr(
        service_mod.client, "activate", lambda *args, **kwargs: _response(now)
    )
    license_service.activate("OAS-KEY")
    assert license_service.has_permission("switch_account")

    license_service.deactivate()
    assert not license_service.has_permission("switch_account")
    assert license_service.status_dict()["state"] == LicenseState.UNLICENSED.value
