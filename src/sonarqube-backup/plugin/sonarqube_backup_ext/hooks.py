"""SonarQube lifecycle hooks - guard and finish every restore.

SonarQube must be stopped while its database is replaced: a running instance
keeps writing to it and keeps serving search indexes that describe the old
data. Two hooks, registered under the ``backuphelper.hooks`` entry-point group:

* ``pre_restore`` refuses the restore while SonarQube still runs. Its embedded
  Elasticsearch locks ``es<N>/node.lock`` on the data volume for as long as it
  runs, so a lock held by another process means SonarQube is up.
* ``post_restore`` drops the search indexes. SonarQube keeps them (Projects
  page, issues, rules, permissions) in Elasticsearch below
  ``<sonarqubeHome>/data/es<N>`` and builds an index only when it does not
  exist. After a database restore the existing indexes still describe the
  database as it was BEFORE the restore: restored projects are missing from the
  Projects page, deleted ones still show up. SonarQube's restore procedure
  therefore drops the indexes before the server starts again:
  https://docs.sonarsource.com/sonarqube-community-build/server-update-and-maintenance/maintenance/backup-and-restore

The compose files mount SonarQube's data volume into the sidecar at
``SONARQUBE_DATA_DIR`` (default ``/sonarqube/data``).
"""

from __future__ import annotations

import errno
import fcntl
import logging
import os
import shutil
from pathlib import Path

log = logging.getLogger("backuphelper.plugin.sonarqube")

DEFAULT_DATA_DIR = "/sonarqube/data"


def data_dir() -> Path:
    return Path(os.environ.get("SONARQUBE_DATA_DIR") or DEFAULT_DATA_DIR)


def held_search_engine_lock(directory: Path) -> Path | None:
    """Return the Elasticsearch node lock below ``directory`` that a running
    process holds, or None when SonarQube's search engine is stopped.

    Elasticsearch 8 locks ``es<N>/node.lock``, Elasticsearch 7 locked
    ``es<N>/nodes/<n>/node.lock``. The file stays behind after a shutdown, so
    only the lock itself tells a running SonarQube from a stopped one."""
    candidates = sorted(directory.glob("es[0-9]*/node.lock"))
    candidates += sorted(directory.glob("es[0-9]*/nodes/*/node.lock"))
    for lock_file in candidates:
        if _locked_by_another_process(lock_file):
            return lock_file
    return None


def _locked_by_another_process(lock_file: Path) -> bool:
    """Probe the lock with a shared lock that is released at once.

    Elasticsearch holds an exclusive POSIX lock on the whole file, so the probe
    fails exactly while it runs. POSIX locks belong to the inode, so the probe
    sees a lock taken in the SonarQube container on the shared volume. A probe
    that cannot run (unreadable file, a filesystem without locks) does not
    block the restore: it is logged, and the documented procedure - stop
    SonarQube first - still applies."""
    try:
        fd = os.open(lock_file, os.O_RDONLY)
    except OSError as exc:
        log.warning("could not open %s to check that SonarQube is stopped: %s", lock_file, exc)
        return False
    try:
        fcntl.lockf(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            return True
        log.warning("could not check the lock on %s: %s", lock_file, exc)
        return False
    finally:
        os.close(fd)  # also releases the probe's own lock
    return False


def drop_search_indexes(directory: Path) -> list[str]:
    """Empty every ``es<N>`` directory below ``directory`` and return their names.

    Only the index directories are touched; heap dumps and anything else on the
    volume stay. Raises when ``directory`` does not exist: the sidecar then has
    no access to SonarQube's data volume, and SonarQube would start on indexes
    that no longer match the restored database."""
    if not directory.is_dir():
        raise RuntimeError(
            f"SonarQube data directory {directory} not found - the search indexes were NOT "
            "dropped. The database restore itself is complete. Mount the SonarQube data "
            "volume into the backup sidecar (see docker-compose.*.yml), or delete the "
            "contents of <sonarqubeHome>/data/es8 by hand before starting SonarQube."
        )
    emptied = []
    for index_dir in sorted(directory.glob("es[0-9]*")):
        if not index_dir.is_dir() or index_dir.is_symlink():
            continue
        for entry in index_dir.iterdir():
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        emptied.append(index_dir.name)
    return emptied


def _refuse_while_sonarqube_runs(context) -> None:
    directory = data_dir()
    if not directory.is_dir():
        # The post_restore hook fails on the same missing mount and names the
        # manual step; here it only means the gate cannot look.
        log.warning("SonarQube data directory %s not found - cannot check that SonarQube "
                    "is stopped; make sure it is before the database is replaced", directory)
        return
    lock = held_search_engine_lock(directory)
    if lock is not None:
        raise RuntimeError(
            f"SonarQube is still running: its search engine holds {lock}. Restore aborted, "
            "the database was not touched. Stop SonarQube first (docker compose -f "
            "<compose file> stop sonarqube), then run the restore again."
        )


def _drop_indexes_after_restore(context) -> None:
    directory = data_dir()
    emptied = drop_search_indexes(directory)
    if emptied:
        log.info("dropped the SonarQube search indexes in %s (%s) - SonarQube rebuilds "
                 "them from the restored database on its next start",
                 directory, ", ".join(emptied))
    else:
        log.info("no SonarQube search index in %s - nothing to drop", directory)


def register(registry) -> None:
    """Entry point for the backuphelper.hooks group."""
    registry.register("pre_restore", _refuse_while_sonarqube_runs)
    registry.register("post_restore", _drop_indexes_after_restore)
