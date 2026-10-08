#!/usr/bin/env bash
# =============================================================================
# XPD-SonarQube backup round trip - shared helpers (sourced, not executed)
# =============================================================================
# Used by seed.sh, mutate.sh and check.sh, which the automation-templates module
# modules-backup-roundtrip-test.yml runs against the started stack. The module
# exports COMPOSE_FILE, COMPOSE_PROJECT_NAME and COMPOSE_PROFILES, so a plain
# `docker compose` reaches this stack, plus ROUNDTRIP_MARKER - a unique token
# ([a-z0-9-]) per run that is used as the key of the seeded SonarQube project.
# =============================================================================

: "${ROUNDTRIP_MARKER:?set by the round-trip module}"

# Errors inside $(...) end the script too, so a failed API call or query can
# never be read as "nothing found".
shopt -s inherit_errexit

# Calls the SonarQube web API from inside the sonarqube container (the stack
# publishes no port on the runner). The remaining arguments go to curl as they
# are, so the marker reaches the API as a URL-encoded form value, never pasted
# into a URL. admin/admin is SonarQube's documented first-boot login; the API
# accepts it before the forced password change, and this throwaway stack is
# never reachable from outside the runner.
sonar_api() {
  local method="$1" path="$2"
  shift 2
  docker compose exec -T sonarqube \
    curl -sS --fail-with-body --max-time 60 -u admin:admin \
    -X "$method" "http://localhost:9000${path}" "$@"
}

# Runs SQL from stdin against the SonarQube database. :'marker' is a psql
# variable, so the value is quoted by psql, not by string pasting. User and
# database come from the postgres container's own environment.
sonar_sql() {
  docker compose exec -T postgres sh -c \
    'exec psql -tA -q -v ON_ERROR_STOP=1 -v marker="$1" -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    _ "$ROUNDTRIP_MARKER"
}
