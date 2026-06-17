"""Backup orchestration: dump → archive → (upload) → retention."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import archive, postgres, retention
from .config import Config

log = logging.getLogger(__name__)


@dataclass
class BackupResult:
    success: bool
    archive_name: str = ""
    archive_bytes: int = 0
    uploaded: bool = False
    pruned_local: int = 0
    pruned_s3: int = 0
    error: str = ""
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.success:
            return f"FAILED: {self.error}"
        mb = self.archive_bytes / (1024 * 1024)
        parts = [f"{self.archive_name} ({mb:.1f} MB)"]
        if self.uploaded:
            parts.append("uploaded to S3")
        parts.append(f"pruned local={self.pruned_local} s3={self.pruned_s3}")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        return "OK: " + ", ".join(parts)


def run_backup(cfg: Config, *, now: datetime | None = None) -> BackupResult:
    """Produce one backup archive and apply retention. Never raises — failures
    are captured in the result so the scheduler/alerting can react."""
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    name = f"{cfg.instance_name}-{stamp}"
    result = BackupResult(success=False, archive_name=f"{name}.tar.gz")

    try:
        cfg.backup_dir.mkdir(parents=True, exist_ok=True)
        archive_path = cfg.backup_dir / f"{name}.tar.gz"

        with tempfile.TemporaryDirectory() as tmp:
            dump_path = Path(tmp) / postgres.dump_filename(cfg)
            postgres.dump(cfg, dump_path)
            manifest = archive.build_manifest(
                instance=cfg.instance_name,
                created_at=now.isoformat(),
                dump_format=cfg.dump_format,
                dump_name=postgres.dump_filename(cfg),
                dump_sha256=archive.sha256_file(dump_path),
                dump_bytes=dump_path.stat().st_size,
            )
            archive.create_archive(dump_path, manifest, archive_path)

        result.archive_bytes = archive_path.stat().st_size
        log.info("archive written: %s (%d bytes)", archive_path.name, result.archive_bytes)

        # Off-site upload (optional)
        if cfg.s3_enabled:
            try:
                from .s3 import S3Target

                target = S3Target(cfg)
                target.upload(archive_path)
                result.uploaded = True
                result.pruned_s3 = len(target.prune(cfg.retention_count))
            except Exception as exc:  # noqa: BLE001
                msg = f"S3 upload/prune failed: {exc}"
                log.error(msg)
                result.warnings.append(msg)

        # Local retention
        if cfg.s3_enabled and not cfg.keep_local_archive and result.uploaded:
            archive_path.unlink(missing_ok=True)
            log.info("local archive removed (KEEP_LOCAL_ARCHIVE=false)")
        else:
            result.pruned_local = len(retention.prune_local(cfg.backup_dir, cfg.retention_count))

        result.success = True
    except Exception as exc:  # noqa: BLE001
        result.error = str(exc)
        log.exception("backup failed")

    return result
