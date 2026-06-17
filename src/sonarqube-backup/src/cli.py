"""Command-line interface for the SonarQube backup sidecar.

    python -m src.main                 # run the scheduler (default)
    python -m src.main --now           # run one backup immediately and exit
    python -m src.main list            # list local archives
    python -m src.main verify <file>   # verify an archive's integrity
    python -m src.main restore <file>  # restore an archive into the database
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import archive, postgres
from .alerting import Alerter
from .backup import run_backup
from .config import Config
from .logging_setup import setup_logging
from .scheduler import run_scheduler

log = logging.getLogger("sonarqube-backup")


def _do_backup_once(cfg: Config) -> int:
    result = run_backup(cfg)
    log.info(result.summary())
    alerter = Alerter(cfg)
    if not result.success:
        alerter.notify("errors", f"[{cfg.instance_name}] backup FAILED", result.error)
        return 1
    if result.warnings:
        alerter.notify(
            "warnings",
            f"[{cfg.instance_name}] backup completed with warnings",
            "\n".join(result.warnings),
        )
    else:
        alerter.notify("all", f"[{cfg.instance_name}] backup OK", result.summary())
    return 0


def _run_scheduler(cfg: Config) -> int:
    if not cfg.schedule_enabled:
        log.warning("SCHEDULE_ENABLED=false — running a single backup instead")
        return _do_backup_once(cfg)
    run_scheduler(cfg, lambda: _do_backup_once(cfg))
    return 0


def _list(cfg: Config) -> int:
    archives = sorted(cfg.backup_dir.glob("*.tar.gz"))
    if not archives:
        log.info("no archives in %s", cfg.backup_dir)
        return 0
    for path in archives:
        mb = path.stat().st_size / (1024 * 1024)
        print(f"{path.name}\t{mb:.1f} MB")
    return 0


def _verify(cfg: Config, target: str) -> int:
    path = _resolve(cfg, target)
    ok = archive.verify_archive(path)
    print(f"{path.name}: {'OK' if ok else 'CORRUPT'}")
    return 0 if ok else 1


def _restore(cfg: Config, target: str) -> int:
    path = _resolve(cfg, target)
    if not archive.verify_archive(path):
        log.error("refusing to restore: %s failed integrity check", path.name)
        return 1
    manifest = archive.read_manifest(path)
    dump_name = manifest["database"]["file"]
    import tempfile
    import tarfile

    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(path, "r:gz") as tar:
            tar.extract(dump_name, tmp)  # noqa: S202 — our own manifest-listed member
        postgres.restore(cfg, Path(tmp) / dump_name)
    log.info("restore complete from %s", path.name)
    return 0


def _resolve(cfg: Config, target: str) -> Path:
    path = Path(target)
    if not path.is_absolute():
        path = cfg.backup_dir / target
    if not path.exists():
        log.error("archive not found: %s", path)
        raise SystemExit(2)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sonarqube-backup")
    parser.add_argument("--now", action="store_true", help="run one backup now and exit")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("schedule", help="run the scheduler (default)")
    sub.add_parser("backup", help="run one backup now and exit")
    sub.add_parser("list", help="list local archives")
    p_verify = sub.add_parser("verify", help="verify an archive's integrity")
    p_verify.add_argument("archive")
    p_restore = sub.add_parser("restore", help="restore an archive into the database")
    p_restore.add_argument("archive")
    args = parser.parse_args(argv)

    cfg = Config.from_env()
    setup_logging(cfg.log_level, cfg.log_format)

    if args.now or args.command == "backup":
        return _do_backup_once(cfg)
    if args.command == "list":
        return _list(cfg)
    if args.command == "verify":
        return _verify(cfg, args.archive)
    if args.command == "restore":
        return _restore(cfg, args.archive)
    return _run_scheduler(cfg)
