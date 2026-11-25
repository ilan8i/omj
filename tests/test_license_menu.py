import module.license as license_pkg
from module.config.config_menu import ConfigMenu


class FakeService:
    def __init__(self, permissions):
        self.permissions = set(permissions)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


def _tasks(menu):
    return [task for tasks in menu.values() for task in tasks]


def test_menu_shows_only_granted_tasks(monkeypatch):
    monkeypatch.setattr(
        license_pkg,
        "license_service",
        FakeService({"switch_account"}),
        raising=False,
    )
    menu = ConfigMenu().gui_menu_list
    tasks = _tasks(menu)
    assert "AccountSwitch" in tasks
    assert "AssistBattle" not in tasks


def test_menu_hides_both_without_permission(monkeypatch):
    monkeypatch.setattr(
        license_pkg,
        "license_service",
        FakeService(set()),
        raising=False,
    )
    menu = ConfigMenu().gui_menu_list
    tasks = _tasks(menu)
    assert "AccountSwitch" not in tasks
    assert "AssistBattle" not in tasks
    # 其它任务仍在
    assert "Orochi" in tasks
