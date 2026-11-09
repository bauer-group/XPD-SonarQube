# SonarQube Community Build — BAUER GROUP Edition

Thin wrapper around the upstream [`sonarqube`](https://hub.docker.com/_/sonarqube)
Community Build image with the
[Community Branch Plugin](https://github.com/mc1arke/sonarqube-community-branch-plugin)
baked in: the image keeps it in `/opt/sonarqube/bundled-plugins/` and its
entrypoint installs it into `/opt/sonarqube/extensions/plugins/` on every start.
After a SonarQube update the entrypoint also starts the database migration the
new version needs, so the update finishes without anyone opening `/setup`.

Published as `ghcr.io/bauer-group/xpd-sonarqube/sonarqube`.

## Why a wrapper image?

* **Reproducible branch analysis.** The branch plugin is version-locked to
  SonarQube. Baking it into the image layer means a rebuild upgrades the plugin
  atomically. The upstream image declares `/opt/sonarqube/extensions` a volume,
  and `docker compose up` carries that anonymous volume over to the recreated
  container on an upgrade — so the entrypoint (`entrypoint.sh`) replaces every
  version of the bundled plugins there with the image's own before SonarQube
  starts. Without it, the first plugin bump would leave the previous version in
  place and SonarQube would not start.
* **Unattended updates.** A SonarQube that finds an older database schema
  waits in maintenance mode (`DB_MIGRATION_NEEDED`, not healthy, unreachable
  behind the proxy) until someone starts the migration. The entrypoint starts
  it itself — see [below](#automatic-database-migration).
* **Sovereign re-publish.** The stack keeps working from our own registry even
  if upstream tags move.

## Automatic database migration

Before it hands over to the upstream entrypoint, `entrypoint.sh` starts a
watcher in the background; SonarQube starts at once, the watcher runs next to
it. It polls `http://localhost:${SONAR_WEB_PORT:-9000}${SONAR_WEB_CONTEXT}/api/system/status`
every 5 seconds, logs each status change to the container log tagged
`[auto-migrate]`, and:

| Status | Watcher |
| --- | --- |
| not answering, `STARTING`, `RESTARTING` | waits |
| `DB_MIGRATION_NEEDED` | POSTs `api/system/migrate_db` (what `/setup` does); an answer without a state — none, a timeout, an error page — is retried while the status stays, 3 POSTs at most |
| `DB_MIGRATION_RUNNING` | waits, never sends anything |
| `UP` | ends |
| `DOWN` — the migration failed | logs an `ERROR` with `api/system/db_migration_status` and ends; nothing retries it |
| `migrate_db` answers `MIGRATION_FAILED` or `NOT_SUPPORTED` | logs an `ERROR` and ends, without another POST |

| Variable | Default | |
| --- | --- | --- |
| `SONARQUBE_AUTO_MIGRATE` | `true` | `false` (also `0`, `no`, `off`): no watcher, a migration waits for `/setup` |
| `SONARQUBE_AUTO_MIGRATE_TIMEOUT_SECONDS` | `3600` | the watcher ends after this many seconds (decimal, up to 9 digits; otherwise a `WARN` and 3600); a running migration goes on |

It only runs when the container starts SonarQube itself, not for another
command (`docker run … <image> bash`). Nothing is backed up before the
migration — the newest restore point is the backup sidecar's last scheduled
snapshot; see [`docs/upgrade.md`](../../docs/upgrade.md#sonarqube-database-migrations)
for backups, starting a migration by hand and rolling back. The watcher is a
child of the SonarQube launcher (PID 1), which does not reap it: once it ended,
it stays a `<defunct>` entry in the process list until the container stops —
one per start, holding no memory or files.

## Versions: pinned in the Dockerfile, auto-maintained

Two explicit build args are the **single source of truth** — and they stay
current automatically, so the Dockerfile always shows what's actually built:

* **`SONARQUBE_VERSION`** (e.g. `26.5.0.122743-community`) — the base image tag.
* **`BRANCH_PLUGIN_VERSION`** (e.g. `26.5.0`) — the branch-plugin release; its
  `MAJOR.MINOR` must equal SonarQube's.
* **`BRANCH_PLUGIN_SHA256`** (optional, empty by default) — supply-chain check of the JAR.

The CI `resolve-versions` job finds the newest **plugin-compatible** pair
(latest branch-plugin release → newest matching `…-community` SonarQube tag),
builds with it, **and commits the pair back into these `ARG` lines** (GITHUB_TOKEN
pushes don't re-trigger CI, so it never loops). The daily base-image monitor
re-runs it on `sonarqube:community` drift. Net effect: published image == this
Dockerfile, always current, fully reproducible — see
[`docs/upgrade.md`](../../docs/upgrade.md).

The plugin JAR is named with its version (`sonarqube-community-branch-plugin-<ver>.jar`)
and the `-javaagent` `ENV` references that exact name.

## Local build & test

```bash
# Builds the pinned pair from the Dockerfile (reproducible, offline):
docker build -t sonarqube-bauer:test ./src/sonarqube

docker run --rm --entrypoint sh sonarqube-bauer:test \
  -c 'ls -l /opt/sonarqube/bundled-plugins/ && echo "$SONAR_WEB_JAVAADDITIONALOPTS"'
```

## License

The wrapper repository is MIT. The contained SonarQube Community Build and the
Community Branch Plugin are both LGPL-3.0.
