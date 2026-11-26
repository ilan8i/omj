# This Python file uses the following encoding: utf-8
"""机器码采集。

机器码只用于授权绑定，客户端只上报 SHA-256 摘要，不上报原始硬件标识。
"""
import ctypes
import hashlib
import os
import subprocess
import sys
import uuid

from module.license.errors import LicenseError, MACHINE_UNAVAILABLE

_machine_code: str | None = None


def _read_machine_guid() -> str:
    """读取 Windows MachineGuid。"""
    if not sys.platform.startswith("win"):
        return ""
    try:
        import winreg

        key_path = r"SOFTWARE\Microsoft\Cryptography"
        access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, access) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return str(value).strip()
    except Exception:
        return ""


def _read_volume_serial() -> str:
    """读取系统盘卷序列号。"""
    if not sys.platform.startswith("win"):
        return ""
    try:
        kernel32 = ctypes.windll.kernel32
        root = (os.environ.get("SystemDrive") or "C:") + "\\"
        serial = ctypes.c_ulong(0)
        success = kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root),
            None,
            0,
            ctypes.byref(serial),
            None,
            None,
            None,
            0,
        )
        if not success:
            return ""
        return f"{serial.value:08X}"
    except Exception:
        return ""


def _read_bios_uuid() -> str:
    """通过 PowerShell 读取 BIOS UUID。

    这里使用 Windows 自带的 powershell.exe，避免要求用户额外安装 pwsh。
    """
    if not sys.platform.startswith("win"):
        return ""
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_ComputerSystemProduct | "
                "Select-Object -ExpandProperty UUID",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return (completed.stdout or "").strip()
    except Exception:
        return ""


def _read_machine_id_non_windows() -> str:
    try:
        with open("/etc/machine-id", "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def compose_machine_code(parts) -> str:
    """把硬件标识组合成 sha256 摘要。

    至少需要两个非空部分，避免单一项缺失时仍然生成可被轻易伪造的机器码。
    """
    values = []
    for part in parts:
        if part is None:
            continue
        value = str(part).strip().upper()
        if value:
            values.append(value)
    if len(values) < 2:
        raise LicenseError(MACHINE_UNAVAILABLE, "无法获取足够的机器标识")
    raw = "|".join(values)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_machine_code() -> str:
    """返回 "sha256:<hex>"，进程内缓存。"""
    global _machine_code
    if _machine_code:
        return _machine_code

    if sys.platform.startswith("win"):
        parts = [_read_machine_guid(), _read_volume_serial(), _read_bios_uuid()]
    else:
        parts = [_read_machine_id_non_windows(), f"{uuid.getnode():012X}"]

    _machine_code = compose_machine_code(parts)
    return _machine_code


def reset_machine_code_cache() -> None:
    """测试用：清空进程内缓存。"""
    global _machine_code
    _machine_code = None


def machine_fingerprint(machine_code: str) -> str:
    """令牌里使用的机器指纹：去掉 sha256: 前缀后取前 16 位。"""
    value = str(machine_code or "").strip().lower()
    if value.startswith("sha256:"):
        value = value[len("sha256:"):]
    return value[:16]
