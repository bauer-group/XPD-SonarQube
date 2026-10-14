# Backup & Restore

The `sonarqube-backup` sidecar dumps the **PostgreSQL database** — the only
stateful component worth backing up. Elasticsearch indexes (`sonarqube-data`)
and plugins (baked into the image) are rebuildable and are not backed up.

Activated by the `backup` compose profile. The sidecar is a meta image on the
central [BackupHelper](https://github.com/bauer-group/cs-backuphelper) engine;
its CLI is `backuphelper` (the container's entrypoint).

## What a backup contains

One snapshot per run, identified by its timestamp (`YYYY-MM-DD_HH-MM-SS`):

- `<id>.tar.gz` — the `pg_dump` of the `sonar` database (component `sonar`,
  `custom` format by default, `plain` via `SONARQUBE_BACKUP_DUMP_FORMAT`;
  `pg_dump` may run for `SONARQUBE_BACKUP_DUMP_TIMEOUT_SECONDS`, default 1800,
  1 to 14400)
- `<id>.manifest.json` — components, sizes and SHA-256 checksums

Snapshots live in the `sonarqube-backup` volume (`/data`) and, if configured, are
uploaded to an external S3 bucket. Retention keeps the newest
`SONARQUBE_BACKUP_RETENTION_COUNT` snapshots locally **and** in S3.

## Scheduling

```ini
SONARQUBE_BACKUP_SCHEDULE_MODE=cron          # or "interval"
SONARQUBE_BACKUP_SCHEDULE_CRON=15 3 * * *    # daily 03:15 (TIME_ZONE)
SONARQUBE_BACKUP_SCHEDULE_INTERVAL_HOURS=24  # used when MODE=interval
SONARQUBE_BACKUP_ON_STARTUP=false
```

Start the scheduler:

```bash
docker compose -f docker-compose.traefik.yml --profile backup up -d
```

The sidecar runs this schedule whenever it is up; there is no switch that keeps
it up without one. For on-demand backups only, leave the `backup` profile off
(`COMPOSE_PROFILES` empty, no `--profile backup up`) and use the `run --rm`
commands below — each starts a one-off sidecar container next to the stack.

## On-demand operations

```bash
# one backup now
docker compose ... --profile backup run --rm sonarqube-backup create

# list local snapshots
docker compose ... --profile backup run --rm sonarqube-backup list

# show a snapshot's components
docker compose ... --profile backup run --rm sonarqube-backup show 2026-06-17_03-15-00

# verify a snapshot's integrity (re-hashes the archive vs. the manifest)
docker compose ... --profile backup run --rm sonarqube-backup verify 2026-06-17_03-15-00
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

> **Destructive.** `restore` drops & recreates objects in the target database;
> objects in `public` the snapshot does not contain are dropped too
> ([over a newer version](#restoring-over-a-newer-sonarqube-version)).
> It refuses to run if the archive fails its SHA-256 integrity check.

```bash
# 1. Verify the snapshot before touching anything
docker compose -f docker-compose.traefik.yml --profile backup run --rm sonarqube-backup verify 2026-06-17_03-15-00

# 2. Stop SonarQube so nothing writes during the restore
docker compose -f docker-compose.traefik.yml stop sonarqube

# 3. Restore the database (and drop the search indexes, see below)
docker compose -f docker-compose.traefik.yml --profile backup run --rm sonarqube-backup restore 2026-06-17_03-15-00 --force

# 4. Start SonarQube; it rebuilds the search indexes from the restored database
docker compose -f docker-compose.traefik.yml up -d sonarqube
```

**SonarQube must be stopped.** `restore` refuses to run while SonarQube is up
and ends with *"SonarQube is still running … Restore aborted, the database was
not touched"* (exit code 1). The sidecar checks the lock that SonarQube's
embedded Elasticsearch holds on `es8/node.lock` in the `sonarqube-data` volume
for as long as it runs; once `docker compose stop sonarqube` has returned, the
lock is gone and the restore goes ahead. Run step 2, then repeat step 3.

**Search indexes.** SonarQube keeps its search indexes (Projects page, issues,
rules) in Elasticsearch below `/opt/sonarqube/data/es8` and only rebuilds an
index that is missing. After a database restore the old indexes would still show
the data as it was before the restore, so
[SonarQube's restore procedure](https://docs.sonarsource.com/sonarqube-community-build/server-update-and-maintenance/maintenance/backup-and-restore)
drops them. The sidecar does this itself: after the database restore it empties
`es8` on the `sonarqube-data` volume, which the compose files mount into it at
`/sonarqube/data`. The next start then reindexes everything — on a large instance
SonarQube takes correspondingly longer to report `UP`.

If `restore` ends with *"search indexes were NOT dropped"*, the sidecar runs from
a compose file without that mount. The database is restored; drop the indexes by
hand before step 4:

```bash
docker compose -f docker-compose.traefik.yml run --rm --no-deps --entrypoint sh sonarqube \
  -c 'rm -rf /opt/sonarqube/data/es8/*'
```

**Which SonarQube to start.** Start the release that ran when the snapshot was
taken, or a newer one within SonarQube's upgrade path, which finds the older
schema and asks for the migration on `/setup`
([upgrade.md](upgrade.md#sonarqube-database-migrations)) — never an older one:
SonarQube refuses to start on a schema newer than itself. To start that very
release, pin `SONARQUBE_VERSION` to its image tag.

**`plain` snapshots.** Only `custom` snapshots (the default) are compared with
the database and replace what is there. A `plain` snapshot
(`SONARQUBE_BACKUP_DUMP_FORMAT=plain`) is replayed through `psql` without
dropping anything and stops at the first *"already exists"*, so it cannot be
restored over the existing database — neither in place nor to roll back an
upgrade. Restore it into an empty database, or keep
`SONARQUBE_BACKUP_DUMP_FORMAT=custom`.

If `restore` ends with *"postgres restore refused: none of the … relation(s) of
schema(s) public in the target database is in sonar.dump"*, the database shares
no table with the snapshot — most likely the stack's postgres volume
(`<STACK_NAME>-postgres`) holds another application's database; check
`STACK_NAME`. The database was not changed; the search indexes are dropped all
the same, and SonarQube rebuilds them on its next start. Restore into an empty
database instead.

### Restoring over a newer SonarQube version

A `custom` snapshot can be restored over a database that a newer SonarQube
migrated after the snapshot — the way back from an upgrade
([upgrade.md](upgrade.md#sonarqube-database-migrations)). `restore` compares the
database with the snapshot first. When `public` holds a table or other object
the snapshot does not contain, it replaces all of `public` in **one**
transaction: it drops every table there, the ones the newer version added
included, and replays the snapshot. Any error rolls everything back. The log
shows the path and, after the commit, what does not come back:

```text
restoring sonar.dump by replacing the … relation(s) of schema(s) public in one transaction
not in the snapshot, dropped: public.…
```

Without such a difference (the snapshot's own tables with changed rows, or an
empty database) it is the plain `pg_restore` as before. Afterwards start the
release that ran when the snapshot was taken (pin `SONARQUBE_VERSION`, see
[upgrade.md](upgrade.md#sonarqube-database-migrations)); a newer one finds the
snapshot's schema and asks for the migration on `/setup` again.

**Sidecar version.** This needs a sidecar on BackupHelper engine 1.10.2 or
later — sidecar release 1.3.21 and later, which `SONARQUBE_BACKUP_VERSION=latest`
(the default) pulls. With an older one such a restore ends with *"cannot drop …
because other objects depend on it"* and rolls back, or leaves the tables the
newer version added behind. Functions, procedures and aggregates the snapshot
does not contain are compared and dropped from engine 1.10.4 on; older engines
leave them in place.

**Own objects are dropped.** The comparison does not tell SonarQube's tables
from yours: a view, table or function you added to `public` of the `sonar`
database after the snapshot (a reporting view, a helper table) is dropped as
well, and so is anything elsewhere that depends on a dropped object, such as a
view on SonarQube's tables in another schema. `not in the snapshot, dropped: …`
lists what does not come back from `public`; a dependent object outside
`public` shows up only among psql's `drop cascades to …` notices in the log,
which also name objects the snapshot recreates right after. Keep such objects
in a separate database, or create them again after the restore.

**Temporary space.** On this path the sidecar first writes the whole database as
uncompressed SQL into its temporary directory, next to the extracted snapshot:
plan about **two to three times the snapshot size** free, more with large binary
columns such as SonarQube's stored source files. That directory is `/tmp` of the
one-off `sonarqube-backup` container; the compose files give it no `tmpfs`, so
it lives on the disk of Docker's data root — as, by default, does the
`sonarqube-backup` volume, so `TMPDIR=/data/tmp` gains nothing there. If that
disk is short, mount a directory with room on another disk into the restore run
and point `TMPDIR` at it. Create the directory first and give it to uid 1000,
the sidecar's user: Docker would create a missing one owned by root, and when
`TMPDIR` is not writable, the engine uses `/tmp` without an error.

```bash
sudo mkdir -p /mnt/scratch/sonarqube-restore
sudo chown 1000:1000 /mnt/scratch/sonarqube-restore
docker compose -f docker-compose.traefik.yml --profile backup run --rm \
  -v /mnt/scratch/sonarqube-restore:/restore-tmp -e TMPDIR=/restore-tmp \
  sonarqube-backup restore 2026-06-17_03-15-00 --force
```

**Database disk.** A restore over an existing database runs in one transaction,
and PostgreSQL frees the files of the dropped tables only at its commit. Until
then the `postgres` volume holds the old and the restored database side by
side, plus WAL: plan about the database's size free there as well — with the
compose defaults on the same Docker disk as the temporary files, so on top of
them. `TMPDIR` on another disk does not free this space.

## Alerting

Alerts are off while `SONARQUBE_BACKUP_ALERT_CHANNELS` is empty (the default).
Naming a channel turns them on:

```ini
SONARQUBE_BACKUP_ALERT_LEVEL=warnings          # errors | warnings | all
SONARQUBE_BACKUP_ALERT_CHANNELS=email,teams    # email,webhook,teams
SONARQUBE_BACKUP_ALERT_EMAIL=ops@example.com    # + SMTP_* for the email channel
SONARQUBE_BACKUP_TEAMS_WEBHOOK=https://...
```

The email channel sends through `SMTP_HOST`/`SMTP_PORT` with STARTTLS while
`SMTP_TLS=true` (the default); `SMTP_TLS=false` sends unencrypted, for a trusted
relay only. Implicit TLS (SMTPS, port 465) is not supported.

## Round-trip test in CI

Every release is gated on a real backup and restore of this stack. The job
`🧪 Backup Round Trip` in [docker-release.yml](../.github/workflows/docker-release.yml)
calls the reusable
[`modules-backup-roundtrip-test.yml`](https://github.com/bauer-group/automation-templates/blob/main/docs/workflows/modules-backup-roundtrip-test.md)
and runs before the release job, which needs it to pass. It also runs when the
base image monitor dispatches a release after a new SonarQube or BackupHelper
engine image, so neither ships before it restored SonarQube data.

| Phase | What happens |
|-------|--------------|
| Build | `src/sonarqube` (with the SonarQube/plugin pair `resolve-versions` picked) and `src/sonarqube-backup` are built from the commit, with fresh base images |
| Start | `docker-compose.coolify.yml` with the `backup` profile and a generated `POSTGRES_PASSWORD` |
| Seed | Through the SonarQube web API: a project whose key and name are the run's marker |
| Back up | `create`, then `show` must list `sonar` without errors or warnings, `verify` must report `OK` |
| Delete | The project, through the web API. Then a `restore <id> --force` while SonarQube still runs must be refused for that reason |
| Restore | `sonarqube` is stopped, `restore <id> --force` runs (database and index drop), the stack is started again |
| Check | The project in the `projects` table, in `api/projects/search` (reads the database) and on the Projects page, `api/components/search_projects` (reads the search index) |

The scripts live in [`tests/backup-roundtrip/`](../tests/backup-roundtrip/). The
check runs three times — before the backup (present), after the deletion (absent)
and after the restore (present) — so a restore that writes nothing cannot pass.
The check after the deletion also proves that the refused restore left the
database alone. The search index check is the one that caught stale indexes
after a restore.

A run takes about 3 minutes (2 min 43 s measured): about 40 s to build both
images, 45 to 50 s for the first boot, 30 to 40 s for the restart with the full
reindex, the rest for the backup and the checks. It starts on pushes to `main` (documentation-only pushes
excluded), on every `workflow_dispatch`, and on pull requests that touch `src/`,
a compose file, `.env.example`, the round-trip scripts or the release workflow.
When it fails, the run's summary names the failed phase, and the
`backup-roundtrip-diagnostics` artifact holds every service's log,
`docker compose ps`, the snapshot list and the manifest.

### Upgrade, off-site copy and compose variants

A second job, `🧪 Backup Round Trip (upgrade, S3, <variant>)`, runs the way
production gets there, once with `docker-compose.coolify.yml` and once with
`docker-compose.traefik.yml`. The release needs both jobs.

| Phase | What happens |
|-------|--------------|
| Previous release | The latest XPD-SonarQube release (`sonarqube` and `sonarqube-backup` images, release tag `vX.Y.Z` → image tag `X.Y.Z`) starts with the compose file of the commit. The module checks that both containers run the release, then the release seeds the project and backs it up with its own sidecar |
| Off-site copy | A throwaway MinIO is the S3 destination (`SONARQUBE_BACKUP_S3_*` point at it); archive and manifest must be in the bucket with the local size |
| Upgrade | [`upgrade.sh`](../tests/backup-roundtrip/upgrade.sh) renames the previous release's branch plugin JAR to a version no image ships — what a SonarQube bump leaves in the `extensions` volume Compose carries over — and starts the database migration watcher. Then the images built from the commit take over `sonarqube:latest` and `sonarqube-backup:latest`, and `docker compose up -d` recreates both containers. Both must then run the build of the commit, compared by the image id tagged before `up`, and SonarQube must start with the plugin of the new image. The project must still be there, and `backuphelper healthcheck` must pass in the new sidecar |
| New host | After the project is deleted, the `sonarqube-backup` container is removed and its data volume emptied; the new sidecar must list the snapshot as `(off-site only)` |
| Restore | The new sidecar restores the **previous release's** snapshot, downloading it from S3 first; the check must find the project again, and the downloaded snapshot must pass `verify` |

**Database migrations.** When the commit moves to a newer SonarQube than the
latest release runs, the new SonarQube finds an older schema and waits in
`DB_MIGRATION_NEEDED` — not `UP`, so not healthy — until someone starts the
migration on `/setup` ([upgrade.md](upgrade.md#sonarqube-database-migrations)).
The restore puts that older schema back, dropping the tables the newer version
added, so it asks again after the restore.
[`migrate-db.sh`](../tests/backup-roundtrip/migrate-db.sh), which `upgrade.sh`
starts in the background, is that operator: whenever SonarQube reports
`DB_MIGRATION_NEEDED`, it calls `POST api/system/migrate_db`, the call `/setup`
makes. It changes nothing else: SonarQube must still become healthy within the
wait timeout, and the check must still find the project. Its log,
`sonarqube-migrate-db.log`, is part of the diagnostics artifact.

The Traefik variant joins the external network `PROXY_NETWORK` names; the job
creates it for the run. Traefik itself is not started, so its routing is not
tested. Each variant uploads its own
`backup-roundtrip-upgrade-<variant>-diagnostics` artifact on failure.

A release exists before its images do: the image jobs push `X.Y.Z` a minute or
two after semantic-release created `vX.Y.Z`. A run that pulls the latest release
in between — or any run after an image job of that release failed — stops at
*Pull previous release* with a message saying so, and the next release waits for
it. Re-run the failed image job (or the round trip once the images are there).
