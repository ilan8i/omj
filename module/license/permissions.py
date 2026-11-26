# This Python file uses the following encoding: utf-8
"""任务级授权权限。

服务端签发令牌时把权限写入 claims.perms，例如：
    "perms": ["switch_account", "assist_battle"]

客户端只做本地校验，不额外发网络请求；权限变更由心跳刷新令牌后生效。
"""
import inflection

PERMISSION_SWITCH_ACCOUNT = "switch_account"
PERMISSION_ASSIST_BATTLE = "assist_battle"

PERMISSION_LABELS = {
    PERMISSION_SWITCH_ACCOUNT: "切换账号",
    PERMISSION_ASSIST_BATTLE: "一键协战",
}

# 任务名使用调度器里的大驼峰名称。
TASK_PERMISSIONS = {
    "AccountSwitch": PERMISSION_SWITCH_ACCOUNT,
    "SwitchAccount": PERMISSION_SWITCH_ACCOUNT,
    "AssistBattle": PERMISSION_ASSIST_BATTLE,
}


def required_permission(task: str) -> str | None:
    """返回任务需要的权限标识；不需要权限时返回 None。"""
    value = str(task or "").strip()
    if not value:
        return None
    permission = TASK_PERMISSIONS.get(value)
    if permission:
        return permission
    return TASK_PERMISSIONS.get(inflection.camelize(value))


def permission_label(permission: str) -> str:
    return PERMISSION_LABELS.get(permission, permission)
