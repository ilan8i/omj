import pytest

from module.license import machine
from module.license.errors import MACHINE_UNAVAILABLE, LicenseError


@pytest.fixture(autouse=True)
def _reset_machine_cache():
    machine.reset_machine_code_cache()
    yield
    machine.reset_machine_code_cache()


def test_machine_code_with_three_parts(monkeypatch):
    monkeypatch.setattr(machine, "_read_machine_guid", lambda: "guid-1")
    monkeypatch.setattr(machine, "_read_volume_serial", lambda: "AABBCCDD")
    monkeypatch.setattr(machine, "_read_bios_uuid", lambda: "bios-uuid")
    code = machine.get_machine_code()
    assert code.startswith("sha256:")
    assert len(code) == len("sha256:") + 64
    assert machine.get_machine_code() == code


def test_machine_code_with_two_parts(monkeypatch):
    monkeypatch.setattr(machine, "_read_machine_guid", lambda: "guid-1")
    monkeypatch.setattr(machine, "_read_volume_serial", lambda: "AABBCCDD")
    monkeypatch.setattr(machine, "_read_bios_uuid", lambda: "")
    assert machine.get_machine_code().startswith("sha256:")


def test_machine_code_with_one_part_raises(monkeypatch):
    monkeypatch.setattr(machine, "_read_machine_guid", lambda: "guid-1")
    monkeypatch.setattr(machine, "_read_volume_serial", lambda: "")
    monkeypatch.setattr(machine, "_read_bios_uuid", lambda: "  ")
    with pytest.raises(LicenseError) as exc:
        machine.get_machine_code()
    assert exc.value.code == MACHINE_UNAVAILABLE


def test_compose_normalizes_values():
    assert machine.compose_machine_code([" a ", "b"]) == machine.compose_machine_code(
        ["A", "B"]
    )


def test_machine_fingerprint():
    fingerprint = machine.machine_fingerprint("sha256:" + "a" * 64)
    assert fingerprint == "a" * 16
