# This Python file uses the following encoding: utf-8
"""授权相关错误。"""

INVALID_KEY = "INVALID_KEY"
MACHINE_MISMATCH = "MACHINE_MISMATCH"
LICENSE_EXPIRED = "LICENSE_EXPIRED"
LICENSE_REVOKED = "LICENSE_REVOKED"
RATE_LIMITED = "RATE_LIMITED"
SERVER_ERROR = "SERVER_ERROR"
NETWORK_ERROR = "NETWORK_ERROR"
TOKEN_INVALID = "TOKEN_INVALID"
TOKEN_EXPIRED = "TOKEN_EXPIRED"
CLOCK_ROLLBACK = "CLOCK_ROLLBACK"
MACHINE_UNAVAILABLE = "MACHINE_UNAVAILABLE"
INSECURE_SERVER = "INSECURE_SERVER"
UNLICENSED = "UNLICENSED"


class LicenseError(Exception):
    """授权流程中的可预期错误。"""

    def __init__(self, code: str, message: str, server_denied: bool = False):
        self.code = code
        self.message = message
        self.server_denied = server_denied
        super().__init__(message)


def is_network_error(exc: BaseException) -> bool:
    return isinstance(exc, LicenseError) and exc.code in (NETWORK_ERROR, SERVER_ERROR)


def is_server_denied(exc: BaseException) -> bool:
    return isinstance(exc, LicenseError) and exc.server_denied
