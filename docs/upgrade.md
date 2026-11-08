# Upgrading

This stack is built to **stay current automatically** — there are no version
numbers to bump by hand.

## How auto-updating works

| Mechanism | What it keeps current |
| --- | --- |
| **CI resolver** (`resolve-versions` in `docker-release.yml`) | On every build, takes the latest Community Branch Plugin release, picks the newest matching `…-community` SonarQube tag, builds and tests with that pair and — once the backup round trips passed with it — **commits it back into the Dockerfile's `ARG` lines** (`pin-versions`, main only), so the Dockerfile is always the current, reproducible source of truth (published == Dockerfile). |
| **Base-image monitor** (`check-base-images.yml`, daily) | Watches the floating tags (`sonarqube:community`, `ghcr.io/bauer-group/cs-backuphelper/backuphelper:latest`, `postgres:18-alpine`, `busybox:stable`) for digest drift and triggers a rebuild/release when upstream moves. |
| **Dependabot** (weekly) | Bumps the base tags inside the Dockerfiles, the compose image tags and the GitHub Actions versions; the `docker-maintenance` workflow auto-merges its patch updates (not GitHub Actions) once `docker-release.yml` passed on the PR, then dispatches `docker-release.yml` on main, which tests the merged commit again and releases it (`fix(docker)` → PATCH). |
| **`docker compose pull`** | Brings the host's pulled images (postgres, busybox, the wrapper images) up to the latest digest of their floating tags. |

So a routine "upgrade" is just: let CI/Dependabot do their thing, then on the
host `docker compose -f docker-compose.traefik.yml pull && up -d`.

## Why the branch plugin needs no manual pin

The Community Branch Plugin is version-locked to SonarQube, and SonarQube's
`community` tag often runs slightly ahead of the plugin's releases. Instead of
pinning, the build **floats on the plugin**: the CI resolver picks the newest
SonarQube version that has a matching plugin, and the Dockerfile derives the
plugin from the base image's `$SONAR_VERSION` (see
[branch-analysis.md](branch-analysis.md)). During the short window after a brand
new SonarQube release but before the matching plugin ships, the resolver simply
stays on the previous (working) version — no breakage, no action needed.

## The two genuinely manual steps

Some upgrades cannot be fully automated because they touch persistent data:

### SonarQube database migrations

SonarQube applies DB migrations on startup. When a new build includes a
migration:

1. **Back up the database first** (`--now`, then `verify`) — see [backup.md](backup.md).
   Note the release that runs, for a rollback (the image tag `X.Y.Z` it was
   built as):

   ```bash
   docker inspect --format '{{ index .Config.Labels "org.opencontainers.image.version" }}' \
     "$(docker compose -f docker-compose.traefik.yml ps -q sonarqube)"
   ```

2. `docker compose -f docker-compose.traefik.yml pull && up -d`.
3. If a migration is required, SonarQube shows a maintenance page — open
   `https://${SONARQUBE_HOSTNAME}/setup` and trigger the upgrade. A release that moves
   to a newer SonarQube is tested this way before it ships: the upgrade round
   trip in CI starts the migration through the API call `/setup` makes (see
   [backup.md](backup.md#upgrade-off-site-copy-and-compose-variants)).
4. Do not skip more than one LTA/major at a time; follow SonarQube's official
   upgrade path for large jumps.

**Rolling back.** To return to the release before, restore the snapshot from
step 1 over the migrated database. Everything since that snapshot is lost:
analyses, projects and settings changed after it do not come back.

1. `docker compose -f docker-compose.traefik.yml stop sonarqube`.
2. `verify` the snapshot, then `restore <id> --force` it with the commands in
   [backup.md](backup.md#restore-disaster-recovery). It needs a `custom`
   snapshot (the default) and a sidecar from release 1.3.21 on
   ([why](backup.md#restoring-over-a-newer-sonarqube-version)). The restore
   drops the tables the newer SonarQube added, logged as
   `not in the snapshot, dropped: …`, and the search indexes; plan free disk
   space of two to three times the snapshot for its temporary files, and about
   the database's size on the `postgres` volume.
3. Pin `SONARQUBE_VERSION` in `.env` to the release noted in step 1 (image tag
   `X.Y.Z` of release `vX.Y.Z`), then
   `docker compose -f docker-compose.traefik.yml up -d sonarqube`. Set it back
   to `latest` once a release fixes the problem. Without the note, the
   [release list](https://github.com/bauer-group/XPD-SonarQube/releases) shows
   which release was the newest when the snapshot was taken — the one that ran,
   if the host had pulled it.

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
