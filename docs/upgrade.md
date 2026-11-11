# Upgrading

This stack is built to **stay current automatically** — there are no version
numbers to bump by hand.

## How auto-updating works

| Mechanism | What it keeps current |
| --- | --- |
| **CI resolver** (`resolve-versions` in `docker-release.yml`) | On every build, takes the latest Community Branch Plugin release, picks the newest matching `…-community` SonarQube tag, builds with that pair **and commits it back into the Dockerfile's `ARG` lines** — so the Dockerfile is always the current, reproducible source of truth (published == Dockerfile). |
| **Base-image monitor** (`check-base-images.yml`, daily) | Watches the floating tags (`sonarqube:community`, `ghcr.io/bauer-group/cs-backuphelper/backuphelper:latest`, `postgres:18-alpine`, `busybox:1`) for digest drift and triggers a rebuild/release when upstream moves. |
| **Dependabot** (weekly) | Bumps the base tags inside the Dockerfiles, the compose image tags and the GitHub Actions versions; the `docker-maintenance` workflow auto-merges its PRs once their checks pass. |
| **`docker compose pull`** | Brings the host's pulled images (postgres, busybox, the wrapper images) up to the latest digest of their floating tags. |

So a routine "upgrade" is just: let CI/Dependabot do their thing, then on the
host `docker compose -f docker-compose.traefik.yml pull && up -d` — the database
migration a new SonarQube needs starts by itself
([below](#sonarqube-database-migrations)).

## Why the branch plugin needs no manual pin

The Community Branch Plugin is version-locked to SonarQube, and SonarQube's
`community` tag often runs slightly ahead of the plugin's releases. Instead of
pinning, the build **floats on the plugin**: the CI resolver picks the newest
SonarQube version that has a matching plugin, and the Dockerfile derives the
plugin from the base image's `$SONAR_VERSION` (see
[branch-analysis.md](branch-analysis.md)). During the short window after a brand
new SonarQube release but before the matching plugin ships, the resolver simply
stays on the previous (working) version — no breakage, no action needed.

## Upgrades that touch persistent data

Two kinds of upgrade change the database. SonarQube's own database migrations
run unattended; a PostgreSQL major upgrade stays a manual step.

### SonarQube database migrations

Nearly every SonarQube version brings a database migration. A SonarQube that
finds an older schema does not migrate by itself: it waits in maintenance mode
(`api/system/status` reports `DB_MIGRATION_NEEDED`) until someone starts the
migration — on `/setup`, or with `POST api/system/migrate_db`. In that state it
is not `UP`, so the healthcheck fails and Traefik/Coolify route nothing to it,
`/setup` included.

**The wrapper image starts the migration itself.** Its entrypoint
([`src/sonarqube/entrypoint.sh`](../src/sonarqube/entrypoint.sh)) runs a watcher
next to SonarQube that polls `api/system/status` inside the container and
logs every status change:

* `DB_MIGRATION_NEEDED` → it POSTs `api/system/migrate_db`, the call `/setup`
  makes. An answer without a state (none, a timeout, an error page) counts as
  not answered: while SonarQube still reports `DB_MIGRATION_NEEDED` it POSTs
  again, 3 times at most, then logs an `ERROR`. An answer `MIGRATION_FAILED` or
  `NOT_SUPPORTED` ends the watcher with an `ERROR` at once;
* `DB_MIGRATION_RUNNING` → it only waits; SonarQube never runs two migrations;
* `UP` → done, the watcher ends;
* `DOWN` (the migration failed) → it logs an `ERROR` with SonarQube's reason and
  stops. Nothing retries a failed migration: SonarQube stays in maintenance mode
  until you roll back (below), or fix the cause and restart the container,
  which tries once more.

So an update — `docker compose pull && up -d`, or a redeploy in Coolify — ends
`UP` without anyone opening `/setup`; SonarQube is unavailable while the
migration runs. The watcher's lines are tagged `[auto-migrate]` in the
SonarQube log:

```bash
docker compose -f docker-compose.traefik.yml logs sonarqube | grep auto-migrate
```

```text
2026.11.09 20:31:03 INFO  [auto-migrate] watching http://localhost:9000/api/system/status for 3600 s; a pending database migration is started automatically (SONARQUBE_AUTO_MIGRATE=false turns this off)
2026.11.09 20:31:03 INFO  [auto-migrate] SonarQube status: not answering yet
2026.11.09 20:32:39 INFO  [auto-migrate] SonarQube status: DB_MIGRATION_NEEDED
2026.11.09 20:32:39 INFO  [auto-migrate] starting the database migration (POST http://localhost:9000/api/system/migrate_db)
2026.11.09 20:32:39 INFO  [auto-migrate] migrate_db: MIGRATION_RUNNING
2026.11.09 20:32:44 INFO  [auto-migrate] SonarQube status: STARTING
2026.11.09 20:33:51 INFO  [auto-migrate] SonarQube status: UP
```

(An upgrade from SonarQube 26.5 to 26.6: 13 migrations, `UP` 72 seconds after
the POST. A short migration can pass between two polls, so
`DB_MIGRATION_RUNNING` may not show.)

| Variable | Default | Effect |
| --- | --- | --- |
| `SONARQUBE_AUTO_MIGRATE` | `true` | `false` turns the watcher off; the migration then waits for you ([by hand](#starting-the-migration-by-hand)) |
| `SONARQUBE_AUTO_MIGRATE_TIMEOUT_SECONDS` | `3600` | How long the watcher follows a start, in whole seconds (up to 9 digits; `0900` is 900); `0` or anything else logs a `WARN` and uses 3600. It only ends the watching: a migration still running goes on |

**Backups — read this before relying on it.** Nothing takes a backup right
before an automatic migration. The newest restore point is the sidecar's last
scheduled backup (daily at 03:15 by default), so a rollback loses everything
since then — up to 24 hours of analyses, projects and settings. Without the
backup sidecar (`COMPOSE_PROFILES` empty) there is none at all. When you need a
closer restore point — a planned update, a large SonarQube jump — take a backup
by hand first and note the release that runs (the image tag `X.Y.Z` it was
built as), then update:

```bash
docker compose -f docker-compose.traefik.yml --profile backup run --rm sonarqube-backup create
docker compose -f docker-compose.traefik.yml --profile backup run --rm sonarqube-backup verify <id>
docker inspect --format '{{ index .Config.Labels "org.opencontainers.image.version" }}' \
  "$(docker compose -f docker-compose.traefik.yml ps -q sonarqube)"
```

The stack also updates by itself (CI, base-image monitor, Dependabot), so an
unplanned update can migrate at any time: set `SONARQUBE_AUTO_MIGRATE=false` if
every migration has to wait for a fresh backup.

#### Starting the migration by hand

With `SONARQUBE_AUTO_MIGRATE=false`, or when the watcher logged an `ERROR` about
`migrate_db`: take the backup above, then start the migration from inside the
container — `/setup` is not reachable through the proxy while SonarQube is not
healthy (the development variant publishes port 9000, where it is):

```bash
docker compose -f docker-compose.traefik.yml exec sonarqube \
  curl -s -X POST http://localhost:9000/api/system/migrate_db
```

A release that moves to a newer SonarQube is tested before it ships: the
upgrade round trip in CI upgrades the latest release to the new images, and
SonarQube has to reach `UP` again with no migration call from outside — at the
upgrade and after the restore of the older snapshot (see
[backup.md](backup.md#upgrade-off-site-copy-and-compose-variants)).

Do not skip more than one LTA/major at a time; follow SonarQube's official
upgrade path for large jumps.

**Rolling back.** To return to the release before, restore the newest
snapshot taken **before the update** — the one by hand, or the last scheduled
one before it — over the migrated database. Not simply the newest snapshot: a
scheduled backup that ran after the update holds the migrated schema, which
the older release refuses to start on, or — after a failed migration — a
half-migrated one. The snapshot id is the time it was taken; compare it with
the first `[auto-migrate]` line of the updated container, or with the time
Compose created that container:

```bash
docker compose -f docker-compose.traefik.yml logs --no-log-prefix sonarqube | grep -m 1 auto-migrate
docker inspect --format '{{ .Created }}' "$(docker compose -f docker-compose.traefik.yml ps -q sonarqube)"
```

(The `[auto-migrate]` lines carry the container's `TIME_ZONE`, `Created` is
UTC.) Everything since that snapshot is lost: analyses, projects and settings
changed after it do not come back.

1. `docker compose -f docker-compose.traefik.yml stop sonarqube`.
2. `verify` the snapshot, then `restore <id> --force` it with the commands in
   [backup.md](backup.md#restore-disaster-recovery). It needs a `custom`
   snapshot (the default) and a sidecar from release 1.3.21 on
   ([why](backup.md#restoring-over-a-newer-sonarqube-version)). The restore
   drops the tables the newer SonarQube added, logged as
   `not in the snapshot, dropped: …`, and the search indexes; plan free disk
   space of two to three times the snapshot for its temporary files, and about
   the database's size on the `postgres` volume.
3. Pin `SONARQUBE_VERSION` in `.env` to the release noted before the update
   (image tag `X.Y.Z` of release `vX.Y.Z`) **before** you start SonarQube again —
   the newer image would migrate the restored database again right away — then
   `docker compose -f docker-compose.traefik.yml up -d sonarqube`. Set it back
   to `latest` once a release fixes the problem. Without the note, the
   [release list](https://github.com/bauer-group/XPD-SonarQube/releases) shows
   which release was the newest when the snapshot was taken — the one that ran,
   if the host had pulled it. In Coolify, set `SONARQUBE_VERSION` in the
   service's environment the same way.

> Only one SonarQube instance may use a database schema at a time. Never run two
> instances against the same database.

### PostgreSQL major upgrades

`POSTGRES_VERSION` is intentionally major-pinned (`18-alpine`) so it patch-floats
but never auto-jumps majors — a major PostgreSQL upgrade is not an in-place
volume swap. To move majors: back up with the sidecar, recreate the `postgres` volume
on the new major, restore. The sidecar's `pg_dump` and `pg_restore` come from the
BackupHelper engine image it is built on (PostgreSQL 18 client tools, see
`PG_CLIENT_VERSION` in [bauer-group/cs-backuphelper](https://github.com/bauer-group/cs-backuphelper)).
`pg_dump` cannot dump a server of a newer major, so before moving to a newer
PostgreSQL major, make sure the engine ships client tools of at least that major.
