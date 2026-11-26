# This Python file uses the following encoding: utf-8
"""本地授权缓存。

缓存使用机器码派生密钥加密，复制到其他机器无法解密。
"""
import hmac
import json
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from module.license import constants
from module.license.machine import get_machine_code

_NONCE_LENGTH = 12


def get_cache_path() -> Path:
    """返回缓存文件路径。"""
    if constants.is_dev():
        override = os.environ.get("OAS_LICENSE_CACHE")
        if override:
            return Path(override)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "OnmyojiAutoScript" / "license.bin"
    return Path.home() / ".oas" / "license.bin"


def _derive_key(machine_code: str) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"oas-license",
        info=b"cache-v1",
    )
    return hkdf.derive(machine_code.encode("utf-8"))


def _cipher() -> AESGCM:
    return AESGCM(_derive_key(get_machine_code()))


def load() -> dict | None:
    """读取并解密缓存；任何异常都返回 None。"""
    try:
        payload = get_cache_path().read_bytes()
        magic = constants.CACHE_MAGIC
        if not payload.startswith(magic):
            return None
        body = payload[len(magic):]
        if len(body) <= _NONCE_LENGTH:
            return None
        nonce = body[:_NONCE_LENGTH]
        ciphertext = body[_NONCE_LENGTH:]
        plaintext = _cipher().decrypt(nonce, ciphertext, magic)
        data = json.loads(plaintext.decode("utf-8"))
        if not isinstance(data, dict):
            return None
        stored_machine = str(data.get("machine_code") or "")
        current_machine = get_machine_code()
        if not stored_machine or not hmac.compare_digest(stored_machine, current_machine):
            return None
        return data
    except Exception:
        return None


def save(data: dict) -> None:
    """加密并原子写入缓存。"""
    if not isinstance(data, dict):
        raise TypeError("license cache must be a dict")
    payload_data = dict(data)
    payload_data["machine_code"] = get_machine_code()
    plaintext = json.dumps(
        payload_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    magic = constants.CACHE_MAGIC
    nonce = secrets.token_bytes(_NONCE_LENGTH)
    ciphertext = _cipher().encrypt(nonce, plaintext, magic)

    path = get_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(magic + nonce + ciphertext)
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def clear() -> None:
    """删除本地缓存。"""
    try:
        get_cache_path().unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass
