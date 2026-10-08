"""Tests for the SonarQube post_restore hook (search index drop)."""

from __future__ import annotations

import pytest

from sonarqube_backup_ext import hooks


class FakeRegistry:
    def __init__(self):
        self.registered = []

    def register(self, phase, hook):
        self.registered.append((phase, hook))


def _sonarqube_data(tmp_path):
    """A data volume as SonarQube leaves it: an es8 index tree plus a heap dump."""
    data = tmp_path / "data"
    (data / "es8" / "indices" / "abc" / "0").mkdir(parents=True)
    (data / "es8" / "indices" / "abc" / "0" / "segment").write_text("x")
    (data / "es8" / "node.lock").write_text("")
    (data / "java_pid1.hprof").write_text("dump")
    return data


def test_register_adds_a_post_restore_hook():
    registry = FakeRegistry()
    hooks.register(registry)
    assert [phase for phase, _ in registry.registered] == ["post_restore"]


def test_drop_empties_the_index_directory_and_keeps_everything_else(tmp_path):
    data = _sonarqube_data(tmp_path)
    assert hooks.drop_search_indexes(data) == ["es8"]
    assert (data / "es8").is_dir()
    assert list((data / "es8").iterdir()) == []
    assert (data / "java_pid1.hprof").read_text() == "dump"


def test_drop_covers_every_index_generation(tmp_path):
    data = _sonarqube_data(tmp_path)
    (data / "es7" / "nodes").mkdir(parents=True)
    assert hooks.drop_search_indexes(data) == ["es7", "es8"]
    assert list((data / "es7").iterdir()) == []


def test_drop_on_a_fresh_volume_is_a_no_op(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    assert hooks.drop_search_indexes(data) == []


def test_drop_without_the_data_volume_fails_loudly(tmp_path):
    with pytest.raises(RuntimeError, match="NOT dropped"):
        hooks.drop_search_indexes(tmp_path / "missing")


def test_post_restore_hook_uses_the_configured_directory(tmp_path, monkeypatch):
    data = _sonarqube_data(tmp_path)
    monkeypatch.setenv("SONARQUBE_DATA_DIR", str(data))
    registry = FakeRegistry()
    hooks.register(registry)
    _, hook = registry.registered[0]
    hook({"job": "main", "snapshot_id": "2026-10-08_12-00-00", "ok": True})
    assert list((data / "es8").iterdir()) == []


def test_default_directory_matches_the_compose_mount(monkeypatch):
    monkeypatch.delenv("SONARQUBE_DATA_DIR", raising=False)
    assert hooks.data_dir().as_posix() == "/sonarqube/data"
