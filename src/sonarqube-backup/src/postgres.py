"""PostgreSQL dump & restore via the bundled pg_dump / pg_restore / psql tools.

The dump itself is always uncompressed here — the orchestrator bundles the
output into a single tar.gz with a manifest. For `custom` format pg_dump already
produces a compact binary file restorable with pg_restore; `plain` produces a
portable .sql restorable with psql.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .config import Config

log = logging.getLogger(__name__)


def _base_env(cfg: Config) -> dict[str, str]:
    """Connection params via libpq environment — never on the argv (ps-safe)."""
    import os

    env = dict(os.environ)
    env.update(
        PGHOST=cfg.db_host,
        PGPORT=str(cfg.db_port),
        PGDATABASE=cfg.db_name,
        PGUSER=cfg.db_user,
        PGPASSWORD=cfg.db_password,
        PGSSLMODE=cfg.db_sslmode,
    )
    return env


def dump_filename(cfg: Config) -> str:
    """Inner filename of the dump within the archive."""
    return "database.dump" if cfg.dump_format == "custom" else "database.sql"


def dump(cfg: Config, dest: Path) -> None:
    """Run pg_dump, writing the dump to `dest`. Raises on failure/timeout."""
    if cfg.dump_format == "custom":
        # -Fc: custom format (compressed, restorable selectively with pg_restore)
        cmd = ["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
               "--file", str(dest)]
    else:
        # -Fp: plain SQL
        cmd = ["pg_dump", "--format=plain", "--no-owner", "--no-privileges",
               "--file", str(dest)]

    log.info("pg_dump → %s (format=%s, db=%s)", dest.name, cfg.dump_format, cfg.db_name)
    try:
        subprocess.run(
            cmd, env=_base_env(cfg), check=True,
            timeout=cfg.dump_timeout_seconds,
            capture_output=True, text=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"pg_dump timed out after {cfg.dump_timeout_seconds}s"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"pg_dump failed: {exc.stderr.strip()}") from exc


def restore(cfg: Config, dump_path: Path) -> None:
    """Restore a dump file back into the configured database.

    DANGER: this writes into the live database. Intended for disaster recovery
    against an empty/standby database. Custom dumps → pg_restore (--clean),
    plain dumps → psql.
    """
    if cfg.dump_format == "custom":
        cmd = ["pg_restore", "--clean", "--if-exists", "--no-owner",
               "--no-privileges", "--dbname", cfg.db_name, str(dump_path)]
    else:
        cmd = ["psql", "--dbname", cfg.db_name, "--file", str(dump_path)]

    log.warning("restoring %s into db=%s (destructive)", dump_path.name, cfg.db_name)
    subprocess.run(cmd, env=_base_env(cfg), check=True, timeout=cfg.dump_timeout_seconds)
