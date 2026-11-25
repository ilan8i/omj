# This Python file uses the following encoding: utf-8
"""授权服务：缓存、状态机与心跳。"""
import asyncio
import json
import random
import sys
import threading
import time
from pathlib import Path
from typing import Awaitable, Callable

from module.license import cache, client, constants
from module.license.errors import (
    CLOCK_ROLLBACK,
    INVALID_KEY,
    LICENSE_REVOKED,
    MACHINE_MISMATCH,
    MACHINE_UNAVAILABLE,
    SERVER_ERROR,
    TOKEN_EXPIRED,
    TOKEN_INVALID,
    LicenseError,
)
from module.license.machine import get_machine_code
from module.license.state import LicenseState, LicenseStatus
from module.license.token import verify_token
from module.logger import logger


class LicenseService:
    """进程内单例。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._status = LicenseStatus()
        self._key = ""
        self._token = ""
        self._plan = ""
        self._token_exp = 0
        self._license_exp = 0
        self._last_server_time = 0
        self._last_ok_at = 0
        self._permissions: set[str] = set()
        self._loaded = False
        self._revoked_notified = False
        self._stop_event = threading.Event()
        self.on_revoked: Callable[[], Awaitable[None]] | None = None

    # ------------------------------------------------------------------ status
    def _snapshot(self) -> LicenseStatus:
        return LicenseStatus(
            state=self._status.state,
            plan=self._status.plan,
            license_exp=self._status.license_exp,
            token_exp=self._status.token_exp,
            last_ok_at=self._status.last_ok_at,
            message=self._status.message,
            permissions=sorted(self._permissions),
        )

    def _set_status(self, state: LicenseState, message: str = "") -> None:
        old_state = self._status.state
        self._status = LicenseStatus(
            state=state,
            plan=self._plan,
            license_exp=self._license_exp,
            token_exp=self._token_exp,
            last_ok_at=self._last_ok_at,
            message=message,
            permissions=sorted(self._permissions),
        )
        if old_state != state:
            text = f"License state: {state.value}"
            if message:
                text += f" | {message}"
            logger.info(text)

    @property
    def token(self) -> str:
        with self._lock:
            return self._token

    def can_run(self) -> bool:
        with self._lock:
            return self._status.can_run()

    def can_start_new_task(self) -> bool:
        return self.can_run()

    def has_permission(self, permission: str) -> bool:
        """当前授权是否包含某项任务权限。"""
        with self._lock:
            return bool(permission) and permission in self._permissions

    @property
    def permissions(self) -> list[str]:
        with self._lock:
            return sorted(self._permissions)

    def status_dict(self) -> dict:
        with self._lock:
            return self._status.to_dict()

    # ------------------------------------------------------------------ cache
    @staticmethod
    def _read_key_file() -> str:
        try:
            data = json.loads(
                Path(constants.LICENSE_KEY_FILE).read_text(encoding="utf-8")
            )
            if isinstance(data, dict):
                return str(data.get("key") or "").strip()
        except Exception:
            pass
        return ""

    def _load_cache_unlocked(self) -> None:
        data = cache.load()
        if isinstance(data, dict):
            self._key = str(data.get("key") or self._key)
            self._token = str(data.get("token") or "")
            self._plan = str(data.get("plan") or "")
            self._last_server_time = int(data.get("last_server_time") or 0)
            self._last_ok_at = int(data.get("last_ok_at") or 0)
        if not self._key:
            self._key = self._read_key_file()

    def load_from_cache(self) -> dict:
        with self._lock:
            if not self._loaded:
                self._loaded = True
                self._load_cache_unlocked()
                self._refresh_from_token()
            return self._status.to_dict()

    def refresh_local(self) -> LicenseStatus:
        """只读本地缓存刷新状态，用于子进程在每个任务前自查。"""
        with self._lock:
            self._loaded = True
            self._load_cache_unlocked()
            self._refresh_from_token()
            return self._snapshot()

    # ------------------------------------------------------------------ state
    def _refresh_from_token(self, allow_grace: bool = True) -> None:
        now = int(time.time())
        self._permissions = set()

        if (
            self._last_server_time
            and now < self._last_server_time - constants.CLOCK_ROLLBACK_TOLERANCE_SECONDS
        ):
            self._set_status(
                LicenseState.CLOCK_ROLLBACK, "本机时间早于授权服务器时间，请校准系统时间"
            )
            return

        if not self._token:
            self._set_status(
                LicenseState.UNLICENSED,
                "尚未激活授权" if self._key else "未填写授权密钥",
            )
            return

        try:
            claims = verify_token(
                self._token, get_machine_code(), check_expiry=False
            )
        except LicenseError as exc:
            if exc.code == MACHINE_UNAVAILABLE:
                self._set_status(LicenseState.UNLICENSED, exc.message)
            elif exc.code == CLOCK_ROLLBACK:
                self._set_status(LicenseState.CLOCK_ROLLBACK, exc.message)
            elif exc.code == MACHINE_MISMATCH:
                self._set_status(LicenseState.REVOKED, exc.message)
            else:
                self._set_status(LicenseState.UNLICENSED, exc.message)
            return
        except Exception as exc:
            self._set_status(
                LicenseState.UNLICENSED,
                f"授权缓存读取失败: {exc.__class__.__name__}",
            )
            return

        self._plan = str(claims.get("plan") or "")
        self._token_exp = int(claims.get("tok_exp") or 0)
        self._license_exp = int(claims.get("lic_exp") or 0)

        raw_permissions = claims.get("perms")
        if isinstance(raw_permissions, (list, tuple, set)):
            self._permissions = {
                str(item).strip()
                for item in raw_permissions
                if str(item).strip()
            }

        if self._license_exp and now >= self._license_exp:
            self._set_status(LicenseState.EXPIRED, "授权已过期")
            return
        if self._token_exp and now < self._token_exp:
            self._set_status(LicenseState.ACTIVE, "")
            return
        if (
            allow_grace
            and self._last_ok_at
            and now <= self._last_ok_at + constants.OFFLINE_GRACE_SECONDS
        ):
            self._set_status(
                LicenseState.GRACE, "授权令牌已过期，正在使用离线宽限期"
            )
            return
        self._set_status(
            LicenseState.EXPIRED, "授权令牌已过期，需要联网刷新"
        )

    def _apply_server_response(self, data: dict, key: str) -> None:
        if not isinstance(data, dict):
            raise LicenseError(SERVER_ERROR, "授权服务返回格式错误")
        token = str(data.get("token") or "")
        if not token:
            with self._lock:
                self._set_status(LicenseState.SERVER_ERROR, "授权服务未返回令牌")
            raise LicenseError(SERVER_ERROR, "授权服务未返回令牌")

        try:
            claims = verify_token(token, get_machine_code(), check_expiry=False)
        except LicenseError:
            with self._lock:
                self._set_status(
                    LicenseState.SERVER_ERROR, "授权服务返回的令牌无效"
                )
            raise

        with self._lock:
            self._key = (key or self._key).strip()
            self._token = token
            self._plan = str(data.get("plan") or claims.get("plan") or "")
            self._token_exp = int(
                data.get("token_exp") or claims.get("tok_exp") or 0
            )
            self._license_exp = int(
                data.get("license_exp") or claims.get("lic_exp") or 0
            )
            self._last_server_time = int(
                data.get("server_time") or time.time()
            )
            self._last_ok_at = self._last_server_time
            self._revoked_notified = False

            try:
                cache.save(
                    {
                        "key": self._key,
                        "token": self._token,
                        "plan": self._plan,
                        "last_server_time": self._last_server_time,
                        "last_ok_at": self._last_ok_at,
                    }
                )
            except Exception as exc:
                logger.warning(
                    f"License cache save failed: {exc.__class__.__name__}"
                )

            self._refresh_from_token()

    # ------------------------------------------------------------------ actions
    def activate(self, key: str) -> LicenseStatus:
        key = (key or "").strip()
        if not key:
            raise LicenseError(INVALID_KEY, "密钥不能为空")

        data = client.activate(
            constants.get_server_url(),
            key,
            get_machine_code(),
            constants.get_app_version(),
        )
        self._apply_server_response(data, key)
        with self._lock:
            return self._snapshot()

    def heartbeat(self) -> LicenseStatus:
        with self._lock:
            if not self._loaded:
                self._loaded = True
                self._load_cache_unlocked()
            token = self._token
            key = self._key

        if not token:
            if key:
                return self.activate(key)
            with self._lock:
                self._set_status(LicenseState.UNLICENSED, "尚未激活授权")
                return self._snapshot()

        try:
            data = client.heartbeat(
                constants.get_server_url(),
                token,
                get_machine_code(),
                constants.get_app_version(),
            )
        except LicenseError as exc:
            # 令牌过期/无效时，用本地保存的密钥重新激活。
            if exc.code in (TOKEN_EXPIRED, TOKEN_INVALID) and key:
                try:
                    return self.activate(key)
                except Exception as activate_exc:
                    with self._lock:
                        state = (
                            LicenseState.EXPIRED
                            if getattr(activate_exc, "server_denied", False)
                            else LicenseState.SERVER_ERROR
                        )
                        self._set_status(
                            state,
                            getattr(
                                activate_exc,
                                "message",
                                activate_exc.__class__.__name__,
                            ),
                        )
                        return self._snapshot()
            with self._lock:
                if exc.server_denied:
                    state = (
                        LicenseState.REVOKED
                        if exc.code in (LICENSE_REVOKED, MACHINE_MISMATCH)
                        else LicenseState.EXPIRED
                    )
                    self._set_status(state, exc.message)
                else:
                    self._refresh_from_token(allow_grace=True)
                    if not self._status.can_run() and self._status.state not in (
                        LicenseState.EXPIRED,
                        LicenseState.REVOKED,
                    ):
                        self._set_status(
                            LicenseState.SERVER_ERROR,
                            f"无法连接授权服务: {exc.message}",
                        )
                return self._snapshot()
        except Exception as exc:
            with self._lock:
                self._refresh_from_token(allow_grace=True)
                if not self._status.can_run() and self._status.state not in (
                    LicenseState.EXPIRED,
                    LicenseState.REVOKED,
                ):
                    self._set_status(
                        LicenseState.SERVER_ERROR,
                        f"授权心跳异常: {exc.__class__.__name__}",
                    )
                return self._snapshot()

        try:
            self._apply_server_response(data, key)
        except LicenseError:
            pass
        with self._lock:
            return self._snapshot()

    def ensure_valid(self, allow_grace: bool = True) -> bool:
        with self._lock:
            if not self._loaded:
                self._loaded = True
                self._load_cache_unlocked()
            self._refresh_from_token(allow_grace=allow_grace)
            can_run = self._status.can_run()
            key = self._key
            has_token = bool(self._token)

        if can_run:
            return True

        if key:
            try:
                self.activate(key)
            except LicenseError as exc:
                logger.warning(f"License activate failed: {exc.code}")
            except Exception as exc:
                logger.warning(
                    f"License activate error: {exc.__class__.__name__}"
                )
            if self.can_run():
                return True

        if has_token:
            self.heartbeat()

        return self.can_run()

    def deactivate(self) -> None:
        with self._lock:
            self._key = ""
            self._token = ""
            self._plan = ""
            self._token_exp = 0
            self._license_exp = 0
            self._last_server_time = 0
            self._last_ok_at = 0
            self._permissions = set()
            self._revoked_notified = False
            cache.clear()
            self._set_status(LicenseState.UNLICENSED, "已清除本地授权")

    # ------------------------------------------------------------------ loop
    def stop(self) -> None:
        self._stop_event.set()

    async def heartbeat_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                status = await asyncio.to_thread(self.heartbeat)
                if (
                    status.state == LicenseState.REVOKED
                    and not self._revoked_notified
                ):
                    self._revoked_notified = True
                    if self.on_revoked is not None:
                        try:
                            await self.on_revoked()
                        except Exception as exc:
                            logger.warning(
                                f"License revoke callback failed: "
                                f"{exc.__class__.__name__}"
                            )
            except Exception as exc:
                logger.warning(
                    f"License heartbeat loop error: {exc.__class__.__name__}"
                )

            delay = constants.HEARTBEAT_INTERVAL_SECONDS + random.uniform(0, 600)
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break


license_service = LicenseService()


def ensure_license_or_exit() -> None:
    if license_service.ensure_valid():
        return
    message = license_service.status_dict().get("message") or "授权无效"
    logger.error(f"授权校验失败: {message}")
    sys.exit(1)
