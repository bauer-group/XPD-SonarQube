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

exit "$FAILED"
