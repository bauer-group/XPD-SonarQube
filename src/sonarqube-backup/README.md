# SonarQube Backup Sidecar

This is now a **thin meta-image** built `FROM
ghcr.io/bauer-group/cs-backuphelper/backuphelper` — the central BackupHelper
engine. All backup logic (pg_dump, retention, manifest, S3, notifications,
restore CLI) lives there; this directory adds SonarQube-specific OCI labels and
one restore hook. Still published as `ghcr.io/bauer-group/xpd-sonarqube/sonarqube-backup`.

## Configuration

The whole backup job is passed inline via the compose service's
`BACKUP_CONFIG_JSON` (see `docker-compose.*.yml`), with secrets kept out of the
rendered config and resolved by the container (`DB_PASSWORD`, `S3_SECRET_KEY`,
`SMTP_PASSWORD`, `WEBHOOK_SECRET`). Tune it through the `SONARQUBE_BACKUP_*`
variables in the repo-level `.env`.

## Restore hook (`plugin/`)

SonarQube keeps its search indexes (Projects page, issues, rules) in
Elasticsearch below `/opt/sonarqube/data/es8` and only builds an index that does
not exist. After a database restore the old indexes would still describe the
database as it was before the restore, so
[SonarQube's restore procedure](https://docs.sonarsource.com/sonarqube-community-build/server-update-and-maintenance/maintenance/backup-and-restore)
drops them before the server starts again.

The `sonarqube_backup_ext` plugin does that step: a `post_restore` hook
(`backuphelper.hooks` entry point) empties the `es<N>` directories of SonarQube's
data volume, which the compose files mount into the sidecar at `/sonarqube/data`
(override with `SONARQUBE_DATA_DIR`). SonarQube rebuilds the indexes from the
restored database on its next start. Nothing from that volume is backed up.

If the volume is not mounted, the hook fails the restore command loudly after the
database is restored, naming the manual step. The plugin's tests run in the
image build's test stage.

See the BackupHelper docs for the config schema, CLI (`list` / `verify` /
`restore`) and channel details:
<https://github.com/bauer-group/cs-backuphelper>
