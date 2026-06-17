# SonarQube Backup Sidecar

Scheduled backup of the SonarQube **PostgreSQL database** — the only stateful
component worth backing up (Elasticsearch indexes and plugins are rebuildable).

Published as `ghcr.io/bauer-group/XPD-SonarQube/sonarqube-backup`.

## What it does

1. `pg_dump` the database (`custom` or `plain` format)
2. bundle the dump + a `manifest.json` (SHA-256, sizes, timestamp) into a `.tar.gz`
3. optionally upload the archive to an off-site S3 bucket
4. prune to the newest `RETENTION_COUNT` archives (local **and** S3)
5. alert on failure/warning via e-mail, webhook and/or Microsoft Teams

## Commands

```bash
# default entrypoint runs the scheduler (cron or interval)
docker compose --profile backup up -d

# one-off backup now
docker compose --profile backup run --rm sonarqube-backup --now

# list / verify / restore archives (paths are relative to /data)
docker compose --profile backup run --rm sonarqube-backup list
docker compose --profile backup run --rm sonarqube-backup verify sonarqube-20260617-031500.tar.gz
docker compose --profile backup run --rm sonarqube-backup restore sonarqube-20260617-031500.tar.gz
```

> `restore` is **destructive** — it drops & recreates objects in the target
> database (`pg_restore --clean` / `psql`). Point it at an empty or standby DB.
> It refuses to run if the archive fails its SHA-256 integrity check.

## Configuration

All settings come from environment variables (see the `SONARQUBE_BACKUP_*` and
`SMTP_*` sections of the repo-level [`.env.example`](../../.env.example), which
the compose files map onto the short names this app reads). Key ones:

| Env                        | Default        | Notes                                    |
| -------------------------- | -------------- | ---------------------------------------- |
| `SCHEDULE_MODE`            | `cron`         | `cron` or `interval`                     |
| `SCHEDULE_CRON`            | `15 3 * * *`   | daily 03:15 in `TZ`                      |
| `DUMP_FORMAT`              | `custom`       | `custom` (pg_restore) or `plain` (psql)  |
| `RETENTION_COUNT`          | `14`           | newest N archives kept                   |
| `S3_ENDPOINT` + `S3_BUCKET`| _(empty)_      | set both to enable off-site upload       |
| `ALERT_CHANNELS`           | _(empty)_      | `email,webhook,teams`                    |

## Notes

* `pg_dump` major version must be **≥** the PostgreSQL server major — the image
  installs `postgresql${PG_MAJOR}-client` (default 18). Bump `PG_MAJOR` together
  with `POSTGRES_VERSION`.
* Tests run during the image build (test-gated) — a failing test fails the build.
