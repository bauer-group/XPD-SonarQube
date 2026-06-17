# Upgrading

## The golden rule: bump SonarQube and the branch plugin as a pair

The Community Branch Plugin is version-locked: plugin `MAJOR.MINOR` must equal
SonarQube `MAJOR.MINOR`. A mismatch stops SonarQube from starting.

1. Find a matching pair:
   - SonarQube Community Build tags: <https://hub.docker.com/_/sonarqube> (look for `…-community`)
   - Plugin releases: <https://github.com/mc1arke/sonarqube-community-branch-plugin/releases>
   - The plugin usually trails the newest SonarQube release by a few weeks — pick
     the newest SonarQube `…-community` tag that has a matching plugin release.
2. Update the pinned defaults in **`src/sonarqube/Dockerfile`**:
   ```dockerfile
   ARG SONARQUBE_VERSION=<new>-community
   ARG BRANCH_PLUGIN_VERSION=<new>
   ```
   and mirror them in **`.env.example`** (`SONARQUBE_BASE_VERSION`,
   `BRANCH_PLUGIN_VERSION`) and **`.github/config/docker-base-image-monitor/base-images.json`**.
3. (Optional, recommended) set `BRANCH_PLUGIN_SHA256` to verify the JAR download.
4. Commit — CI rebuilds and republishes `ghcr.io/bauer-group/XPD-SonarQube/sonarqube`.

## SonarQube upgrade procedure

SonarQube applies database migrations on startup. For a safe upgrade:

1. **Back up the database first** (`--now`, then `verify`) — see [backup.md](backup.md).
2. Pull/deploy the new wrapper image and recreate the `sonarqube` service.
3. Watch the logs; if a DB migration is required, SonarQube serves a maintenance
   page — open `https://${SONARQUBE_HOSTNAME}/setup` and trigger the upgrade.
4. Do **not** skip across more than one LTA/major at a time — follow SonarQube's
   official upgrade path if jumping several majors.

> Only one SonarQube instance may use a database schema at a time. Never run two
> instances (e.g. old + new) against the same database.

## PostgreSQL upgrade

`POSTGRES_VERSION` (and the backup image's `PG_MAJOR` build arg) should stay
within SonarQube's supported PostgreSQL range. A PostgreSQL **major** upgrade is
not an in-place volume swap — dump (with the backup sidecar), recreate the `db`
volume on the new major, and restore.

## Base image digest drift

`check-base-images.yml` runs daily and, when an upstream base image digest moves
on a watched tag (`python:3.13-alpine`, `postgres:16-alpine`, …), triggers
`docker-release.yml` with `force-release` to rebuild and republish — no manual
action needed.
