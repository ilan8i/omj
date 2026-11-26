# This Python file uses the following encoding: utf-8
"""授权模块的固定配置。

授权服务地址和 Ed25519 公钥随代码一起发布，用户不需要自己创建配置文件。
用户卡密通过 POST /license/activate 输入；也可以可选地写到
config/license.json 的 key 字段（该文件已被 .gitignore 忽略）。

只有设置 OAS_LICENSE_DEV=1 且 DEV_MODE=True 时，才允许用环境变量覆盖。
"""
import base64
import os

# 授权服务地址与公钥。
LICENSE_SERVER = "https://license.556523.xyz"
LICENSE_PUBLIC_KEY_B64 = "64GiJWL15TKWO_y9q6JpGrG1IHRIyFNkTYILZDjydGQ"

# 可选的本机卡密文件；config/*.json 已被 .gitignore 忽略。
LICENSE_KEY_FILE = "config/license.json"

# 授权令牌与离线宽限。
TOKEN_TTL_SECONDS = 7 * 86400
OFFLINE_GRACE_SECONDS = 7 * 86400
HEARTBEAT_INTERVAL_SECONDS = 6 * 3600
CLOCK_ROLLBACK_TOLERANCE_SECONDS = 600

# 缓存文件魔数。
CACHE_MAGIC = b"OASL1"

# 发布构建必须保持 False。
# 本地联调（例如连本地假授权服务）时，在开发分支把它改成 True，
# 再配合 OAS_LICENSE_DEV=1 使用。不要只靠环境变量开启，否则任何人都能
# 用 OAS_LICENSE_DEV=1 覆盖服务地址和公钥。
DEV_MODE = False


def is_dev() -> bool:
    """是否处于本地联调模式。"""
    return DEV_MODE and os.environ.get("OAS_LICENSE_DEV") == "1"


def get_server_url() -> str:
    """返回授权服务地址。"""
    if is_dev():
        return (os.environ.get("OAS_LICENSE_SERVER") or LICENSE_SERVER).strip()
    return LICENSE_SERVER


def get_public_key_b64() -> str:
    """返回 Ed25519 公钥（base64url，无 padding）。"""
    if is_dev():
        return (
            os.environ.get("OAS_LICENSE_PUBLIC_KEY") or LICENSE_PUBLIC_KEY_B64
        ).strip()
    return LICENSE_PUBLIC_KEY_B64


def get_public_key_bytes() -> bytes:
    """返回 raw 32 字节公钥；未配置时返回空 bytes。"""
    value = get_public_key_b64()
    if not value:
        return b""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def get_app_version() -> str:
    """上报给授权服务的客户端版本号。"""
    return os.environ.get("OAS_APP_VERSION", "0.0.0").strip() or "0.0.0"
