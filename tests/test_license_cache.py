from pathlib import Path

from module.license import cache


def test_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "get_cache_path", lambda: tmp_path / "license.bin")
    monkeypatch.setattr(cache, "get_machine_code", lambda: "sha256:" + "a" * 64)

    data = {"key": "OMJ-TEST", "token": "t", "last_ok_at": 123}
    cache.save(data)
    loaded = cache.load()
    assert loaded["key"] == "OMJ-TEST"
    assert loaded["token"] == "t"


def test_copy_to_other_machine_cannot_decrypt(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "get_cache_path", lambda: tmp_path / "license.bin")
    monkeypatch.setattr(cache, "get_machine_code", lambda: "sha256:" + "a" * 64)
    cache.save({"key": "OMJ-TEST"})

    monkeypatch.setattr(cache, "get_machine_code", lambda: "sha256:" + "b" * 64)
    assert cache.load() is None


def test_tampered_file_returns_none(tmp_path, monkeypatch):
    path = tmp_path / "license.bin"
    monkeypatch.setattr(cache, "get_cache_path", lambda: path)
    monkeypatch.setattr(cache, "get_machine_code", lambda: "sha256:" + "a" * 64)
    path.write_bytes(b"OASL1" + b"x" * 40)
    assert cache.load() is None


def test_clear(tmp_path, monkeypatch):
    path = tmp_path / "license.bin"
    monkeypatch.setattr(cache, "get_cache_path", lambda: path)
    monkeypatch.setattr(cache, "get_machine_code", lambda: "sha256:" + "a" * 64)
    cache.save({"key": "OMJ-TEST"})
    assert path.exists()
    cache.clear()
    assert not path.exists()
    assert cache.load() is None


def test_atomic_write_leaves_no_tmp_file(tmp_path, monkeypatch):
    path = tmp_path / "license.bin"
    monkeypatch.setattr(cache, "get_cache_path", lambda: path)
    monkeypatch.setattr(cache, "get_machine_code", lambda: "sha256:" + "a" * 64)
    cache.save({"key": "OMJ-TEST"})
    assert list(Path(tmp_path).glob("*.tmp")) == []
