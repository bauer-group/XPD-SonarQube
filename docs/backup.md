# Backup & Restore

The `sonarqube-backup` sidecar dumps the **PostgreSQL database** — the only
stateful component worth backing up. Elasticsearch indexes (`sonarqube-data`)
and plugins (baked into the image) are rebuildable and are not backed up.

Activated by the `backup` compose profile.

## What a backup contains

A single `.tar.gz` per run, named `<instance>-YYYYmmdd-HHMMSS.tar.gz`, holding:

- the `pg_dump` output (`database.dump` for `custom`, `database.sql` for `plain`)
- a `manifest.json` with the SHA-256, byte size, format and timestamp

Archives live in the `sonarqube-backup` volume (`/data`) and, if configured, are
uploaded to an external S3 bucket. Retention keeps the newest
`SONARQUBE_BACKUP_RETENTION_COUNT` archives locally **and** in S3.

## Scheduling

```ini
SONARQUBE_BACKUP_SCHEDULE_ENABLED=true
SONARQUBE_BACKUP_SCHEDULE_MODE=cron          # or "interval"
SONARQUBE_BACKUP_SCHEDULE_CRON=15 3 * * *    # daily 03:15 (TIME_ZONE)
SONARQUBE_BACKUP_ON_STARTUP=false
```

Start the scheduler:

```bash
docker compose -f docker-compose.traefik.yml --profile backup up -d
```

## On-demand operations

```bash
# one backup now
docker compose ... --profile backup run --rm sonarqube-backup --now

# list local archives
docker compose ... --profile backup run --rm sonarqube-backup list

# verify an archive's integrity (re-hashes the dump vs. the manifest)
docker compose ... --profile backup run --rm sonarqube-backup verify sonarqube-20260617-031500.tar.gz
```

## Off-site target (optional)

Set both to enable S3 upload (any S3-compatible endpoint, e.g. MinIO):

```ini
SONARQUBE_BACKUP_S3_ENDPOINT=https://s3.example.com
SONARQUBE_BACKUP_S3_BUCKET=backups
SONARQUBE_BACKUP_S3_ACCESS_KEY=...
SONARQUBE_BACKUP_S3_SECRET_KEY=...
SONARQUBE_BACKUP_S3_PREFIX=sonarqube/
```

## Restore (disaster recovery)

> **Destructive.** `restore` drops & recreates objects in the target database.
> Point it at an empty or standby database. It refuses to run if the archive
> fails its SHA-256 integrity check.

```bash
# 1. Stop SonarQube so nothing writes during the restore
docker compose -f docker-compose.traefik.yml stop sonarqube

# 2. (custom format) restore into the live DB
docker compose ... --profile backup run --rm sonarqube-backup restore sonarqube-20260617-031500.tar.gz

# 3. Start SonarQube; it rebuilds the Elasticsearch indexes from the DB on boot
docker compose -f docker-compose.traefik.yml up -d sonarqube
```

A SonarQube database restore must target the **same SonarQube major version**
that produced it — restore the DB, then start a matching SonarQube image.

## Alerting

```ini
SONARQUBE_BACKUP_ALERT_ENABLED=true
SONARQUBE_BACKUP_ALERT_LEVEL=warnings          # errors | warnings | all
SONARQUBE_BACKUP_ALERT_CHANNELS=email,teams    # email,webhook,teams
SONARQUBE_BACKUP_ALERT_EMAIL=ops@example.com    # + SMTP_* for the email channel
SONARQUBE_BACKUP_TEAMS_WEBHOOK=https://...
```
