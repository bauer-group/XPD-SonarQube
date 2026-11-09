#!/bin/bash
# =============================================================================
# SonarQube wrapper entrypoint — installs the bundled plugins on every start
# and starts a pending database migration
# =============================================================================
# The upstream image declares /opt/sonarqube/extensions a VOLUME, so every
# container gets an anonymous volume there, and `docker compose up` hands the
# old container's anonymous volumes to the new one when it recreates it for an
# image upgrade. The new container would then see the PREVIOUS image's plugins:
# after a plugin bump the -javaagent JAR this image's ENV names is missing and
# SonarQube does not start ("Error opening zip file … branch-plugin-<new>.jar").
#
# So the image keeps its plugins outside the volume, in
# /opt/sonarqube/bundled-plugins, and this script replaces every version of
# them in extensions/plugins with the bundled ones before SonarQube starts.
# Plugins this image does not bundle stay untouched. Then it hands over to the
# upstream entrypoint with the same arguments.
#
# Database migration: nearly every SonarQube version brings one. A SonarQube
# that finds an older schema waits in DB_MIGRATION_NEEDED until someone POSTs
# api/system/migrate_db (what /setup does) - not UP, so not healthy, and the
# reverse proxy routes nothing to it, /setup included. This stack updates
# itself (docs/upgrade.md), so the update would end in an outage until someone
# starts the migration inside the container. auto_migrate below does that step:
# started in the background before the exec, it polls api/system/status and
# POSTs migrate_db when SonarQube asks for it - see auto_migrate for the
# rules. SONARQUBE_AUTO_MIGRATE=false turns it off. The last backup before an
# automatic migration is the latest scheduled one (docs/upgrade.md).
# =============================================================================
set -euo pipefail

BUNDLED=/opt/sonarqube/bundled-plugins
PLUGINS="${SQ_EXTENSIONS_DIR:-/opt/sonarqube/extensions}/plugins"

mkdir -p "$PLUGINS"
# Every version of a plugin this image manages - also one it no longer
# bundles (INCLUDE_OIDC_PLUGIN=false).
rm -f "$PLUGINS"/sonarqube-community-branch-plugin-*.jar \
      "$PLUGINS"/sonar-auth-oidc-plugin-*.jar
cp "$BUNDLED"/*.jar "$PLUGINS"/

# ── Automatic database migration ─────────────────────────────────────────────
# Runs next to SonarQube, never in front of it: the exec below starts SonarQube
# at once, and this process lives on as a child of the new PID 1 (the
# SonarQube launcher). Its lines go to the container log, tagged
# [auto-migrate]. The rules:
#   * while SonarQube starts, api/system/status does not answer yet - that is
#     waiting, never an error (set +e: the script's errexit is off in here)
#   * DB_MIGRATION_NEEDED -> a POST of api/system/migrate_db; SonarQube only
#     starts a migration from that state and never runs two at once. An answer
#     without a "state" (none, a curl timeout, an HTTP error page) counts as
#     not answered yet: while the status stays DB_MIGRATION_NEEDED the watcher
#     POSTs again, MAX_POSTS times in all, then stops with an ERROR
#   * DB_MIGRATION_RUNNING -> nothing is sent, only the status is logged
#   * DOWN (the migration failed), or a migrate_db answer that names another
#     state than running/succeeded (MIGRATION_FAILED, NOT_SUPPORTED) -> an
#     ERROR and the watcher stops at once: SonarQube only retries after a
#     restart, and nothing here restarts it
#   * UP -> done; after SONARQUBE_AUTO_MIGRATE_TIMEOUT_SECONDS it stops anyway
#     (a migration still running then goes on, only the logging ends)
# The launcher does not reap children it did not start, so the finished
# watcher stays a <defunct> process entry until the container stops - one per
# container start, without memory or open files.
MAX_POSTS=3

auto_migrate() {
  set +e
  local base="http://localhost:${SONAR_WEB_PORT:-9000}${SONAR_WEB_CONTEXT:-}"
  base="${base%/}/api/system"
  # Decimal digits only, at most 9: 10# reads a leading zero (0900) as decimal,
  # where bash arithmetic would take it for octal and end the watcher.
  local raw="${SONARQUBE_AUTO_MIGRATE_TIMEOUT_SECONDS:-3600}" timeout=0
  case "$raw" in
    '' | *[!0-9]* | ??????????*) ;;
    *) timeout=$((10#$raw)) ;;
  esac
  if [ "$timeout" -eq 0 ]; then
    log WARN "SONARQUBE_AUTO_MIGRATE_TIMEOUT_SECONDS='$raw' is no positive number of seconds (at most 9 digits), using 3600"
    timeout=3600
  fi
  local deadline=$((SECONDS + timeout)) status="" last="-" answer=""
  local posts=0 started=false

  log INFO "watching $base/status for $timeout s; a pending database migration is started automatically (SONARQUBE_AUTO_MIGRATE=false turns this off)"
  while [ "$SECONDS" -lt "$deadline" ]; do
    status=$(curl -s --max-time 10 "$base/status" | json_value status)
    if [ "$status" != "$last" ]; then
      log INFO "SonarQube status: ${status:-not answering yet}"
      last="$status"
    fi
    case "$status" in
      UP)
        return 0 ;;
      DB_MIGRATION_NEEDED)
        # Once migrate_db answered "running" or "succeeded", SonarQube moves on
        # to DB_MIGRATION_RUNNING by itself: nothing more is sent.
        if [ "$started" = false ]; then
          if [ "$posts" -ge "$MAX_POSTS" ]; then
            log ERROR "migrate_db answered none of $MAX_POSTS POSTs and SonarQube still waits in DB_MIGRATION_NEEDED"
            log ERROR "SonarQube stays in maintenance mode; start the migration by hand (docs/upgrade.md)"
            return 1
          fi
          posts=$((posts + 1))
          migrate_db "$base" "$posts"
          case $? in
            0) started=true ;;
            1) return 1 ;;
          esac
        fi ;;
      DOWN)
        answer=$(curl -s --max-time 10 "$base/db_migration_status")
        log ERROR "SonarQube is DOWN - the database migration FAILED: ${answer:-no details, see the log above}"
        log ERROR "Nothing retries it. Roll back with the last backup (docs/upgrade.md, Rolling back), or fix the cause and restart the container to try once more"
        return 1 ;;
    esac
    sleep 5
  done
  log WARN "stopped watching after $timeout s, last status: ${last:-not answering}; a running migration goes on (api/system/db_migration_status)"
  return 1
}

# POSTs api/system/migrate_db, attempt $2 of MAX_POSTS. Returns 0 when the
# answer says the migration runs or ran, 2 when it names no state (POST again
# while SonarQube still asks), 1 when it names any other state (stop).
migrate_db() {
  local base="$1" attempt="$2" answer state
  if [ "$attempt" -eq 1 ]; then
    log INFO "starting the database migration (POST $base/migrate_db)"
  else
    log INFO "starting the database migration again, attempt $attempt of $MAX_POSTS (POST $base/migrate_db)"
  fi
  # One line, so an HTML error page stays one log line; cut to 300 characters
  # once the state is read.
  answer=$(curl -s --max-time 60 -X POST "$base/migrate_db" | tr '\r\n' '  ')
  state=$(json_value state <<< "$answer")
  answer="${answer:0:300}"
  case "$state" in
    MIGRATION_RUNNING | MIGRATION_SUCCEEDED | NO_MIGRATION)
      log INFO "migrate_db: $state"
      return 0 ;;
    '')
      local next="POSTing again while SonarQube still reports DB_MIGRATION_NEEDED"
      [ "$attempt" -lt "$MAX_POSTS" ] || next="that was the last attempt"
      log WARN "migrate_db attempt $attempt of $MAX_POSTS: no state in the answer (${answer:-no answer}); $next"
      return 2 ;;
  esac
  log ERROR "migrate_db did not start the migration: $answer"
  log ERROR "SonarQube stays in maintenance mode; start the migration by hand (docs/upgrade.md)"
  return 1
}

# The value of a flat JSON string field on stdin ("status", "state"), or nothing.
json_value() { sed -n "s/.*\"$1\":\"\([A-Z_]*\)\".*/\1/p"; }

log() { printf '%s %-5s [auto-migrate] %s\n' "$(date '+%Y.%m.%d %H:%M:%S')" "$1" "$2"; }

# Only when SonarQube itself starts: upstream runs any other command instead
# (the same check as /opt/sonarqube/docker/entrypoint.sh).
if [ "$#" -eq 0 ] || [ "${1#-}" != "$1" ]; then
  case "${SONARQUBE_AUTO_MIGRATE:-true}" in
    [Ff][Aa][Ll][Ss][Ee] | 0 | [Nn][Oo] | [Oo][Ff][Ff])
      log INFO "off (SONARQUBE_AUTO_MIGRATE=${SONARQUBE_AUTO_MIGRATE}): a pending database migration waits for /setup or POST api/system/migrate_db" ;;
    *)
      auto_migrate < /dev/null & ;;
  esac
fi

exec /opt/sonarqube/docker/entrypoint.sh "$@"
