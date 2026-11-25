# This Python file uses the following encoding: utf-8
"""授权状态与对外展示结构。"""
from dataclasses import dataclass
from enum import Enum
import time


class LicenseState(str, Enum):
    UNLICENSED = "unlicensed"
    ACTIVE = "active"
    GRACE = "grace"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SERVER_ERROR = "server_error"
    CLOCK_ROLLBACK = "clock_rollback"


@dataclass
class LicenseStatus:
    state: LicenseState = LicenseState.UNLICENSED
    plan: str = ""
    license_exp: int = 0
    token_exp: int = 0
    last_ok_at: int = 0
    message: str = ""

    @property
    def remaining_seconds(self) -> int:
        if not self.license_exp:
            return 0
        return max(0, int(self.license_exp) - int(time.time()))

    def can_run(self) -> bool:
        return self.state in (LicenseState.ACTIVE, LicenseState.GRACE)

    def can_start_new_task(self) -> bool:
        return self.can_run()

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "plan": self.plan,
            "license_exp": int(self.license_exp or 0),
            "token_exp": int(self.token_exp or 0),
            "remaining_seconds": self.remaining_seconds,
            "last_ok_at": int(self.last_ok_at or 0),
            "message": self.message,
        }
