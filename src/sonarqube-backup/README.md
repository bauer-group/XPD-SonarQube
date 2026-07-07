# SonarQube Backup Sidecar

This is now a **thin meta-image** built `FROM
ghcr.io/bauer-group/cs-backuphelper/backuphelper` — the central BackupHelper
engine. All backup logic (pg_dump, retention, manifest, S3, notifications,
restore CLI) lives there; this directory only adds SonarQube-specific OCI
labels. Still published as `ghcr.io/bauer-group/xpd-sonarqube/sonarqube-backup`.

## Configuration

The whole backup job is passed inline via the compose service's
`BACKUP_CONFIG_JSON` (see `docker-compose.*.yml`), with secrets kept out of the
rendered config and resolved by the container (`DB_PASSWORD`, `S3_SECRET_KEY`,
`SMTP_PASSWORD`, `WEBHOOK_SECRET`). Tune it through the `SONARQUBE_BACKUP_*`
variables in the repo-level `.env`.

See the BackupHelper docs for the config schema, CLI (`list` / `verify` /
`restore`) and channel details:
<https://github.com/bauer-group/cs-backuphelper>
