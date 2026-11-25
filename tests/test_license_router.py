import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module.license.errors import INVALID_KEY, MACHINE_MISMATCH, LicenseError
from module.license.state import LicenseState, LicenseStatus
from module.server import license_router


class FakeService:
    def __init__(self, state=LicenseState.ACTIVE, activate_error=None):
        self.state = state
        self.activate_error = activate_error
        self.deactivated = False

    def status_dict(self):
        return {
            "state": self.state.value,
            "plan": "month_30d",
            "license_exp": int(time.time()) + 86400,
            "token_exp": int(time.time()) + 3600,
            "remaining_seconds": 86400,
            "last_ok_at": int(time.time()),
            "message": "",
        }

    def can_start_new_task(self):
        return self.state in (LicenseState.ACTIVE, LicenseState.GRACE)

    def activate(self, key):
        if self.activate_error is not None:
            raise self.activate_error
        self.state = LicenseState.ACTIVE
        return LicenseStatus(
            state=LicenseState.ACTIVE,
            plan="month_30d",
            license_exp=int(time.time()) + 86400,
            token_exp=int(time.time()) + 3600,
            last_ok_at=int(time.time()),
        )

    def heartbeat(self):
        return LicenseStatus(
            state=self.state,
            plan="month_30d",
            license_exp=int(time.time()) + 86400,
            token_exp=int(time.time()) + 3600,
            last_ok_at=int(time.time()),
        )

    def deactivate(self):
        self.deactivated = True
        self.state = LicenseState.UNLICENSED


@pytest.fixture()
def client(monkeypatch):
    fake = FakeService()
    monkeypatch.setattr(license_router, "license_service", fake)
    app = FastAPI()
    app.include_router(license_router.license_app)
    return TestClient(app), fake


def test_status(client):
    http, fake = client
    response = http.get("/license/status")
    assert response.status_code == 200
    assert response.json()["license"]["state"] == "active"


def test_activate_success(client):
    http, fake = client
    response = http.post("/license/activate", json={"key": "OAS-TEST"})
    assert response.status_code == 200
    assert response.json()["code"] == "OK"


def test_activate_invalid_key(client, monkeypatch):
    http, fake = client
    fake.activate_error = LicenseError(INVALID_KEY, "bad key")
    response = http.post("/license/activate", json={"key": "bad"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == INVALID_KEY


def test_activate_machine_mismatch(client):
    http, fake = client
    fake.activate_error = LicenseError(
        MACHINE_MISMATCH, "bound", server_denied=True
    )
    response = http.post("/license/activate", json={"key": "OAS-TEST"})
    assert response.status_code == 409


def test_deactivate(client):
    http, fake = client
    response = http.post("/license/deactivate")
    assert response.status_code == 200
    assert fake.deactivated is True
    assert response.json()["license"]["state"] == "unlicensed"


def test_script_start_returns_402(monkeypatch):
    from module.server import script_router

    class FakeMM:
        script_process = {}

    fake = FakeService(state=LicenseState.UNLICENSED)
    monkeypatch.setattr(script_router, "license_service", fake)
    monkeypatch.setattr(script_router, "mm", FakeMM())

    app = FastAPI()
    app.include_router(script_router.script_app)
    http = TestClient(app)
    response = http.get("/oas/start")
    assert response.status_code == 402
