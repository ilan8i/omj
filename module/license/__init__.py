# This Python file uses the following encoding: utf-8
"""OAS 授权模块。

许可证服务需要读取日志等运行时依赖，因此这里延迟导入，避免测试
token/cache/machine 时被无关依赖拖累。
"""
from module.license.state import LicenseState, LicenseStatus

__all__ = [
    "LicenseState",
    "LicenseStatus",
    "license_service",
    "ensure_license_or_exit",
]


def __getattr__(name):
    if name == "license_service":
        from module.license.service import license_service

        return license_service
    if name == "ensure_license_or_exit":
        from module.license.service import ensure_license_or_exit

        return ensure_license_or_exit
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
