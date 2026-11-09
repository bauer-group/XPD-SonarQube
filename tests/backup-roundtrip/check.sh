#!/usr/bin/env bash
# =============================================================================
# XPD-SonarQube backup round trip - check
# =============================================================================
# Exits 0 when the seeded project is in the state ROUNDTRIP_EXPECT names
# (present or absent) in each of the three places SonarQube keeps it:
#   1. the projects table in PostgreSQL (what the backup holds)
#   2. the web API that reads the database (api/projects/search)
#   3. the web API that reads the Elasticsearch index (api/components/
#      search_projects, the Projects page) - SonarQube does not back up its
#      index, so after a restore it must have been rebuilt from the database
# Each place is checked on its own: "absent" proves the deletion reached all of
# them, "present" proves the restore brought the project back everywhere.
#
# On an image built from this commit it also checks the database migration
# watcher (src/sonarqube/entrypoint.sh) of the container's latest start - see
# check_auto_migrate below. That covers the start after the upgrade and the
# one after the restore, which both migrate when the commit moves to a newer
# SonarQube.
# =============================================================================
set -euo pipefail
# shellcheck source=tests/backup-roundtrip/common.sh
source "$(dirname "$0")/common.sh"

case "${ROUNDTRIP_EXPECT:?set by the round-trip module}" in
  present) WANT=1 ;;
  absent)  WANT=0 ;;
  *) echo "unknown ROUNDTRIP_EXPECT '$ROUNDTRIP_EXPECT'" >&2; exit 2 ;;
esac
FAILED=0

# Which SonarQube answers: the previous release's before an upgrade, this
# commit's after it.
echo "SonarQube $(sonar_api GET /api/server/version)"

expect_count() {
  local what="$1" got="$2"
  if [ "$got" = "$WANT" ]; then
    echo "ok   $what: $got (expected $WANT)"
  else
    echo "FAIL $what: $got (expected $WANT)"; FAILED=1
  fi
}

# -- database (component "sonar") ---------------------------------------------
ROWS=$(sonar_sql <<'SQL'
SELECT count(*) FROM projects WHERE kee = :'marker';
SQL
)
expect_count "project row in PostgreSQL" "$ROWS"

# -- SonarQube, read from the database ------------------------------------------
TOTAL=$(sonar_api GET /api/projects/search -G --data-urlencode "projects=${ROUNDTRIP_MARKER}" \
  | jq -r '.paging.total')
expect_count "project in api/projects/search" "$TOTAL"

# -- SonarQube, read from the search index ---------------------------------------
# Indexing follows the database within a second or two, so this one waits for
# the expected state - bounded, and an API error still ends the check at once.
INDEX_TIMEOUT=120
DEADLINE=$((SECONDS + INDEX_TIMEOUT))
while :; do
  INDEXED=$(sonar_api GET /api/components/search_projects -G --data-urlencode "ps=500" \
    | jq --arg key "$ROUNDTRIP_MARKER" '[.components[] | select(.key == $key)] | length')
  if [ "$INDEXED" = "$WANT" ] || [ "$SECONDS" -ge "$DEADLINE" ]; then
    break
  fi
  sleep 2
done
expect_count "project on the Projects page (search index)" "$INDEXED"

# -- the database migration watcher ---------------------------------------------
# Skipped only when the container provably runs the previous release of an
# upgrade round trip (its image id), which may not have the watcher yet; any
# other image is this commit's build and must pass. Each container start logs
# an "[auto-migrate] watching" line (or "off"); the lines from the latest one
# on must hold no ERROR and end in "SonarQube status: UP". The stack is
# healthy (UP) by now, so the watcher, which polls every 5 s, logs UP within a
# few seconds - a watcher that died, like on an unreadable timeout, does not.
WATCHER_TIMEOUT=60

# The [auto-migrate] lines of the container's latest start.
watcher_lines() {
  docker logs "$1" 2>&1 | awk '
    /\[auto-migrate\] (watching|off) / { lines = "" }
    /\[auto-migrate\]/ { lines = lines $0 ORS }
    END { printf "%s", lines }'
}

check_auto_migrate() {
  local container running previous="" previous_id="" lines deadline
  container=$(docker compose ps -q sonarqube)
  if [ -z "$container" ]; then
    echo "FAIL [auto-migrate] watcher: no sonarqube container"; FAILED=1; return
  fi
  running=$(docker inspect --format '{{.Image}}' "$container")
  # {"service": "previous release image"}, set by the module for upgrade-from;
  # a lookup that fails ends the check (errexit), it never skips it.
  if [ -n "${ROUNDTRIP_PREVIOUS_IMAGES:-}" ]; then
    previous=$(jq -r '.sonarqube // empty' <<< "$ROUNDTRIP_PREVIOUS_IMAGES")
  fi
  if [ -n "$previous" ]; then
    previous_id=$(docker image inspect --format '{{.Id}}' "$previous")
  fi
  if [ -n "$previous_id" ] && [ "$running" = "$previous_id" ]; then
    echo "skip [auto-migrate] watcher: sonarqube runs the previous release $previous"
    return
  fi

  deadline=$((SECONDS + WATCHER_TIMEOUT))
  while :; do
    lines=$(watcher_lines "$container")
    if [[ "$lines" == *"[auto-migrate] SonarQube status: UP"* || "$lines" == *"ERROR [auto-migrate]"* ]] ||
       [ "$SECONDS" -ge "$deadline" ]; then
      break
    fi
    sleep 2
  done
  [ -z "$lines" ] || printf '%s\n' "$lines" | sed 's/^/  | /'

  if [ -z "$lines" ]; then
    echo "FAIL [auto-migrate] watcher: no [auto-migrate] line in the sonarqube log - the watcher did not start"; FAILED=1
  elif [[ "$lines" == *"[auto-migrate] off "* ]]; then
    echo "FAIL [auto-migrate] watcher: off in the latest start (SONARQUBE_AUTO_MIGRATE)"; FAILED=1
  elif [[ "$lines" == *"ERROR [auto-migrate]"* ]]; then
    echo "FAIL [auto-migrate] watcher: logged an ERROR in the latest start (lines above)"; FAILED=1
  elif [[ "$lines" != *"[auto-migrate] SonarQube status: UP"* ]]; then
    echo "FAIL [auto-migrate] watcher: no 'SonarQube status: UP' within ${WATCHER_TIMEOUT} s, although SonarQube is healthy"; FAILED=1
  elif [[ "$lines" == *"[auto-migrate] starting the database migration"* ]]; then
    echo "ok   [auto-migrate] watcher: started the database migration, SonarQube UP"
  else
    echo "ok   [auto-migrate] watcher: SonarQube UP, no migration needed"
  fi
}
check_auto_migrate

exit "$FAILED"
