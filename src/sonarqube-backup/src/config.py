"""Configuration for the SonarQube backup sidecar — loaded from env vars.

Pure stdlib (no pydantic) to keep the image small. All values come from the
environment; the compose files map the user-facing SONARQUBE_BACKUP_* names
onto the short internal names read here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

Env = Mapping[str, str]


def _bool(env: Env, key: str, default: bool = False) -> bool:
    v = env.get(key)
    if v is None or v.strip() == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(env: Env, key: str, default: int) -> int:
    v = env.get(key)
    if v is None or v.strip() == "":
        return default
    try:
        return int(v.strip())
    except ValueError:
        return default


def _str(env: Env, key: str, default: str = "") -> str:
    v = env.get(key)
    return default if v is None else v


def _csv(env: Env, key: str) -> tuple[str, ...]:
    raw = _str(env, key).strip()
    if not raw:
        return ()
    return tuple(part.strip().lower() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class Config:
    instance_name: str

    # Source database
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_sslmode: str

    # Dump + retention
    dump_format: str          # "custom" | "plain"
    dump_timeout_seconds: int
    retention_count: int
    keep_local_archive: bool
    backup_dir: Path

    # Schedule
    schedule_enabled: bool
    schedule_mode: str        # "cron" | "interval"
    schedule_cron: str
    schedule_interval_hours: int
    run_on_startup: bool

    # Off-site S3 target
    s3_endpoint: str
    s3_bucket: str
    s3_access_key: str
    s3_secret_key: str
    s3_region: str
    s3_prefix: str
    s3_max_workers: int

    # Alerting
    alert_enabled: bool
    alert_level: str          # "errors" | "warnings" | "all"
    alert_channels: tuple[str, ...]
    alert_email: str
    smtp_host: str
    smtp_port: int
    smtp_secure: str          # "starttls" | "ssl" | "none"
    smtp_username: str
    smtp_password: str
    smtp_from: str
    webhook_url: str
    webhook_secret: str
    teams_webhook_url: str

    # Logging
    log_level: str
    log_format: str           # "console" | "json"

    @property
    def s3_enabled(self) -> bool:
        """Off-site upload is active only when an endpoint AND bucket are set."""
        return bool(self.s3_endpoint and self.s3_bucket)

    @property
    def timezone(self) -> str:
        return os.environ.get("TZ", "Etc/UTC")

    @classmethod
    def from_env(cls, env: Env | None = None) -> "Config":
        env = os.environ if env is None else env
        return cls(
            instance_name=_str(env, "INSTANCE_NAME", "sonarqube"),
            db_host=_str(env, "DB_HOST", "db"),
            db_port=_int(env, "DB_PORT", 5432),
            db_name=_str(env, "DB_NAME", "sonar"),
            db_user=_str(env, "DB_USER", "sonar"),
            db_password=_str(env, "DB_PASSWORD"),
            db_sslmode=_str(env, "DB_SSLMODE", "disable"),
            dump_format=_str(env, "DUMP_FORMAT", "custom").strip().lower(),
            dump_timeout_seconds=_int(env, "DUMP_TIMEOUT_SECONDS", 1800),
            retention_count=_int(env, "RETENTION_COUNT", 14),
            keep_local_archive=_bool(env, "KEEP_LOCAL_ARCHIVE", True),
            backup_dir=Path(_str(env, "BACKUP_DIR", "/data")),
            schedule_enabled=_bool(env, "SCHEDULE_ENABLED", True),
            schedule_mode=_str(env, "SCHEDULE_MODE", "cron").strip().lower(),
            schedule_cron=_str(env, "SCHEDULE_CRON", "15 3 * * *"),
            schedule_interval_hours=_int(env, "SCHEDULE_INTERVAL_HOURS", 24),
            run_on_startup=_bool(env, "RUN_ON_STARTUP", False),
            s3_endpoint=_str(env, "S3_ENDPOINT"),
            s3_bucket=_str(env, "S3_BUCKET"),
            s3_access_key=_str(env, "S3_ACCESS_KEY"),
            s3_secret_key=_str(env, "S3_SECRET_KEY"),
            s3_region=_str(env, "S3_REGION", "eu-central-1"),
            s3_prefix=_str(env, "S3_PREFIX", "sonarqube/"),
            s3_max_workers=_int(env, "S3_MAX_WORKERS", 4),
            alert_enabled=_bool(env, "ALERT_ENABLED", False),
            alert_level=_str(env, "ALERT_LEVEL", "warnings").strip().lower(),
            alert_channels=_csv(env, "ALERT_CHANNELS"),
            alert_email=_str(env, "ALERT_EMAIL"),
            smtp_host=_str(env, "SMTP_HOST"),
            smtp_port=_int(env, "SMTP_PORT", 587),
            smtp_secure=_str(env, "SMTP_SECURE", "starttls").strip().lower(),
            smtp_username=_str(env, "SMTP_USERNAME"),
            smtp_password=_str(env, "SMTP_PASSWORD"),
            smtp_from=_str(env, "SMTP_FROM"),
            webhook_url=_str(env, "WEBHOOK_URL"),
            webhook_secret=_str(env, "WEBHOOK_SECRET"),
            teams_webhook_url=_str(env, "TEAMS_WEBHOOK_URL"),
            log_level=_str(env, "LOG_LEVEL", "INFO").strip().upper(),
            log_format=_str(env, "LOG_FORMAT", "console").strip().lower(),
        )
