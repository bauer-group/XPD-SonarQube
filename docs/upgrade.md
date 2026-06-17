# Upgrading

This stack is built to **stay current automatically** — there are no version
numbers to bump by hand.

## How auto-updating works

| Mechanism | What it keeps current |
| --- | --- |
| **CI resolver** (`resolve-versions` in `docker-release.yml`) | On every build, takes the latest Community Branch Plugin release and rebuilds the wrapper on the newest matching `…-community` SonarQube tag. Always the freshest WORKING pair. |
| **Base-image monitor** (`check-base-images.yml`, daily) | Watches the floating tags (`sonarqube:community`, `python:3.14-alpine`, `postgres:18-alpine`, `busybox:stable`) for digest drift and triggers a rebuild/release when upstream moves. |
| **Dependabot** (weekly) | Bumps the floating base tags inside the Dockerfiles and the Python deps; the `docker-maintenance` workflow auto-merges Dockerfile bumps. |
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
2. `docker compose -f docker-compose.traefik.yml pull && up -d`.
3. If a migration is required, SonarQube shows a maintenance page — open
   `https://${SONARQUBE_HOSTNAME}/setup` and trigger the upgrade.
4. Do not skip more than one LTA/major at a time; follow SonarQube's official
   upgrade path for large jumps.

> Only one SonarQube instance may use a database schema at a time. Never run two
> instances against the same database.

### PostgreSQL major upgrades

`POSTGRES_VERSION` is intentionally major-pinned (`18-alpine`) so it patch-floats
but never auto-jumps majors — a major PostgreSQL upgrade is not an in-place
volume swap. To move majors: back up with the sidecar, recreate the `postgres` volume
on the new major, restore. Keep the backup image's `PG_MAJOR` build arg in step.
