"""SonarQube lifecycle hook - drops the search indexes after every restore.

SonarQube keeps its search indexes (Projects page, issues, rules, permissions)
in Elasticsearch below ``<sonarqubeHome>/data/es<N>`` and builds an index only
when it does not exist. After a database restore the existing indexes still
describe the database as it was BEFORE the restore: restored projects are
missing from the Projects page, deleted ones still show up. SonarQube's restore
procedure therefore drops the indexes before the server starts again:
https://docs.sonarsource.com/sonarqube-community-build/server-update-and-maintenance/maintenance/backup-and-restore

Registered under the ``backuphelper.hooks`` entry-point group. The compose files
mount SonarQube's data volume into the sidecar at ``SONARQUBE_DATA_DIR``
(default ``/sonarqube/data``). SonarQube must be stopped during the restore -
it is anyway, nothing may write to the database while it is replaced.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

log = logging.getLogger("backuphelper.plugin.sonarqube")

DEFAULT_DATA_DIR = "/sonarqube/data"


def data_dir() -> Path:
    return Path(os.environ.get("SONARQUBE_DATA_DIR") or DEFAULT_DATA_DIR)


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
    registry.register("post_restore", _drop_indexes_after_restore)
