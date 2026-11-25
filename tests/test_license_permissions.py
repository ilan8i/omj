from module.license.permissions import (
    PERMISSION_ASSIST_BATTLE,
    PERMISSION_SWITCH_ACCOUNT,
    permission_label,
    required_permission,
)


def test_task_permission_mapping():
    assert required_permission("AccountSwitch") == PERMISSION_SWITCH_ACCOUNT
    assert required_permission("SwitchAccount") == PERMISSION_SWITCH_ACCOUNT
    assert required_permission("AssistBattle") == PERMISSION_ASSIST_BATTLE
    assert required_permission("Orochi") is None
    assert required_permission("") is None
    assert required_permission(None) is None


def test_permission_label():
    assert permission_label(PERMISSION_SWITCH_ACCOUNT) == "切换账号"
    assert permission_label(PERMISSION_ASSIST_BATTLE) == "一键协战"
    assert permission_label("unknown") == "unknown"
