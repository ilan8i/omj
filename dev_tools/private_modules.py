# This Python file uses the following encoding: utf-8
"""需要 Cython 编译的模块清单。"""

MODULES = [
    # 授权实现
    "module/license/cache.py",
    "module/license/client.py",
    "module/license/constants.py",
    "module/license/errors.py",
    "module/license/machine.py",
    "module/license/permissions.py",
    "module/license/service.py",
    "module/license/state.py",
    "module/license/token.py",
    # 服务端授权接口
    "module/server/license_router.py",
    # 入口
    "script.py",
    "server.py",
]
