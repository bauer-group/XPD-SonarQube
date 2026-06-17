"""Retention: keep the newest N archives, prune the rest (local + S3)."""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

ARCHIVE_GLOB = "*.tar.gz"


def select_expired(names: list[str], keep: int) -> list[str]:
    """Given archive names (lexically sortable by the timestamp prefix), return
    the ones to delete so that `keep` newest remain. keep<=0 keeps everything."""
    if keep <= 0:
        return []
    # Names are `<instance>-YYYYmmdd-HHMMSS.tar.gz` → lexical sort == chronological.
    ordered = sorted(names)
    if len(ordered) <= keep:
        return []
    return ordered[: len(ordered) - keep]


def prune_local(directory: Path, keep: int) -> list[Path]:
    """Delete expired local archives. Returns the deleted paths."""
    archives = [p.name for p in directory.glob(ARCHIVE_GLOB)]
    expired = select_expired(archives, keep)
    deleted: list[Path] = []
    for name in expired:
        path = directory / name
        try:
            path.unlink()
            deleted.append(path)
            log.info("retention: pruned local %s", name)
        except OSError as exc:
            log.warning("retention: could not delete %s: %s", name, exc)
    return deleted
