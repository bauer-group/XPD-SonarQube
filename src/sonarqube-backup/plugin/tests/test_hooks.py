"""Tests for the SonarQube restore hooks (running-SonarQube gate, index drop)."""

from __future__ import annotations

import subprocess
import sys
from contextlib import contextmanager

import pytest

from sonarqube_backup_ext import hooks


class FakeRegistry:
    def __init__(self):
        self.registered = []

    def register(self, phase, hook):
        self.registered.append((phase, hook))

    def hook(self, phase):
        return next(hook for registered, hook in self.registered if registered == phase)


def _sonarqube_data(tmp_path):
    """A data volume as SonarQube leaves it: an es8 index tree plus a heap dump."""
    data = tmp_path / "data"
    (data / "es8" / "indices" / "abc" / "0").mkdir(parents=True)
    (data / "es8" / "indices" / "abc" / "0" / "segment").write_text("x")
    (data / "es8" / "node.lock").write_text("")
    (data / "java_pid1.hprof").write_text("dump")
    return data


# Takes an exclusive lock on the whole file, like Elasticsearch's node lock,
# and holds it until stdin closes.
_LOCK_HOLDER = """
import fcntl, sys
with open(sys.argv[1], "a") as lock_file:
    fcntl.lockf(lock_file, fcntl.LOCK_EX)
    print("locked", flush=True)
    sys.stdin.read()
"""


@contextmanager
def held_by_another_process(path):
    """Hold ``path`` locked from a second process, as a running SonarQube does.
    POSIX locks never conflict within one process, so the test needs two."""
    holder = subprocess.Popen([sys.executable, "-c", _LOCK_HOLDER, str(path)],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "locked"
        yield
    finally:
        holder.stdin.close()
        holder.wait(timeout=10)


def test_register_adds_the_gate_and_the_index_drop():
    registry = FakeRegistry()
    hooks.register(registry)
    assert [phase for phase, _ in registry.registered] == ["pre_restore", "post_restore"]


# -- pre_restore: refuse while SonarQube runs -----------------------------------

def test_gate_passes_when_sonarqube_is_stopped(tmp_path, monkeypatch):
    data = _sonarqube_data(tmp_path)  # node.lock left behind, nobody holds it
    monkeypatch.setenv("SONARQUBE_DATA_DIR", str(data))
    registry = FakeRegistry()
    hooks.register(registry)
    registry.hook("pre_restore")({"job": "main", "snapshot_id": "2026-10-08_12-00-00"})


def test_gate_refuses_while_sonarqube_runs_and_changes_nothing(tmp_path, monkeypatch):
    data = _sonarqube_data(tmp_path)
    monkeypatch.setenv("SONARQUBE_DATA_DIR", str(data))
    registry = FakeRegistry()
    hooks.register(registry)
    with held_by_another_process(data / "es8" / "node.lock"):
        with pytest.raises(RuntimeError, match="SonarQube is still running"):
            registry.hook("pre_restore")({"job": "main", "snapshot_id": "2026-10-08_12-00-00"})
    assert (data / "es8" / "indices" / "abc" / "0" / "segment").read_text() == "x"


def test_gate_passes_again_once_sonarqube_stopped(tmp_path):
    data = _sonarqube_data(tmp_path)
    with held_by_another_process(data / "es8" / "node.lock"):
        assert hooks.held_search_engine_lock(data) == data / "es8" / "node.lock"
    assert hooks.held_search_engine_lock(data) is None


def test_gate_covers_the_elasticsearch_7_layout(tmp_path):
    data = tmp_path / "data"
    lock = data / "es7" / "nodes" / "0" / "node.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("")
    with held_by_another_process(lock):
        assert hooks.held_search_engine_lock(data) == lock


def test_gate_on_a_fresh_volume_passes(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    assert hooks.held_search_engine_lock(data) is None


def test_gate_without_the_data_volume_does_not_block(tmp_path, monkeypatch, caplog):
    # The post_restore hook fails on the missing mount and names the manual step.
    monkeypatch.setenv("SONARQUBE_DATA_DIR", str(tmp_path / "missing"))
    registry = FakeRegistry()
    hooks.register(registry)
    registry.hook("pre_restore")({"job": "main", "snapshot_id": "2026-10-08_12-00-00"})
    assert "cannot check that SonarQube is stopped" in caplog.text


# -- post_restore: drop the search indexes --------------------------------------

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
    registry.hook("post_restore")({"job": "main", "snapshot_id": "2026-10-08_12-00-00", "ok": True})
    assert list((data / "es8").iterdir()) == []


def test_default_directory_matches_the_compose_mount(monkeypatch):
    monkeypatch.delenv("SONARQUBE_DATA_DIR", raising=False)
    assert hooks.data_dir().as_posix() == "/sonarqube/data"
