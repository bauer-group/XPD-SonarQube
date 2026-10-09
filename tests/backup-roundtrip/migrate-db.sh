#!/usr/bin/env bash
# =============================================================================
# XPD-SonarQube backup round trip - database migration watcher
# =============================================================================
# Started in the background by upgrade.sh; does what docs/upgrade.md tells the
# operator to do on /setup. Whenever the sonarqube container of the compose
# project $1 reports DB_MIGRATION_NEEDED, it starts the migration through the
# web API call /setup makes (POST api/system/migrate_db), and logs every status
# change. It changes nothing else: the stack must still become healthy within
# the module's wait timeout, and the check must still find the project.
#
# Stops after $2 seconds (default 3600); the runner stops it at the end of the
# job anyway. A container that is restarting or not up yet is skipped, never
# an error.
# =============================================================================
set -uo pipefail

PROJECT="${1:?compose project name}"
DEADLINE=$((SECONDS + ${2:-3600}))

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }

LAST=""
while [ "$SECONDS" -lt "$DEADLINE" ]; do
  CONTAINER=$(docker ps -q \
    --filter "label=com.docker.compose.project=$PROJECT" \
    --filter "label=com.docker.compose.service=sonarqube" 2> /dev/null | head -n 1)
  STATUS=""
  if [ -n "$CONTAINER" ]; then
    STATUS=$(docker exec "$CONTAINER" curl -s --max-time 10 http://localhost:9000/api/system/status 2> /dev/null \
      | sed -n 's/.*"status":"\([A-Z_]*\)".*/\1/p')
  fi
  if [ -n "$STATUS" ] && [ "$CONTAINER $STATUS" != "$LAST" ]; then
    log "sonarqube ${CONTAINER:0:12}: $STATUS"
    LAST="$CONTAINER $STATUS"
  fi
  if [ "$STATUS" = "DB_MIGRATION_NEEDED" ]; then
    log "starting the database migration (POST api/system/migrate_db)"
    docker exec "$CONTAINER" curl -s --max-time 30 -X POST http://localhost:9000/api/system/migrate_db || true
    echo
  fi
  sleep 5
done
log "stopped after the deadline"
