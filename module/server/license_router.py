# This Python file uses the following encoding: utf-8
"""授权相关 API。

注意：这里刻意不使用 ApiLoggingRoute。该路由会把请求体写进 api 日志，
而 /license/activate 的请求体包含用户密钥。
"""
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from module.license import license_service
from module.license.errors import (
    INVALID_KEY,
    LICENSE_EXPIRED,
    LICENSE_REVOKED,
    MACHINE_MISMATCH,
    MACHINE_UNAVAILABLE,
    NETWORK_ERROR,
    RATE_LIMITED,
    SERVER_ERROR,
    UNLICENSED,
    LicenseError,
)
from module.logger import logger

license_app = APIRouter(prefix="/license", tags=["license"])

_ERROR_STATUS = {
    INVALID_KEY: 400,
    UNLICENSED: 400,
    LICENSE_REVOKED: 403,
    MACHINE_MISMATCH: 409,
    LICENSE_EXPIRED: 410,
    RATE_LIMITED: 429,
    SERVER_ERROR: 503,
    NETWORK_ERROR: 503,
    MACHINE_UNAVAILABLE: 500,
}


class ActivateRequest(BaseModel):
    key: str


def _raise_license_error(exc: LicenseError) -> None:
    raise HTTPException(
        status_code=_ERROR_STATUS.get(exc.code, 400),
        detail={
            "code": exc.code,
            "message": exc.message,
            "license": license_service.status_dict(),
        },
    )


@license_app.get("/status")
async def license_status():
    return {"code": "OK", "license": license_service.status_dict()}


@license_app.post("/activate")
async def license_activate(request: ActivateRequest):
    try:
        status = await asyncio.to_thread(license_service.activate, request.key)
    except LicenseError as exc:
        logger.warning(f"License activate rejected: {exc.code}")
        _raise_license_error(exc)
    return {
        "code": "OK",
        "message": "激活成功",
        "license": status.to_dict(),
    }


@license_app.post("/heartbeat")
async def license_heartbeat():
    status = await asyncio.to_thread(license_service.heartbeat)
    return {"code": "OK", "license": status.to_dict()}


@license_app.post("/deactivate")
async def license_deactivate():
    license_service.deactivate()
    return {
        "code": "OK",
        "message": "已清除本地授权",
        "license": license_service.status_dict(),
    }
