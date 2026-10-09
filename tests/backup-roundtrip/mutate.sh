#!/usr/bin/env bash
# =============================================================================
# XPD-SonarQube backup round trip - mutate
# =============================================================================
# Deletes the seeded project the way a user does: through the SonarQube web
# API, which removes it from PostgreSQL and from the search index. The restore
# has to bring it back in both.
#
# SonarQube is still running at this point, so a restore must be refused (the
# sidecar's pre_restore gate). This script tries one and fails unless the
# restore is refused for exactly that reason. The module's check afterwards
# (expects the project absent) proves that the refused restore did not touch
# the database.
# =============================================================================
set -euo pipefail
# shellcheck source=tests/backup-roundtrip/common.sh
source "$(dirname "$0")/common.sh"
: "${ROUNDTRIP_SNAPSHOT_ID:?set by the round-trip module}"
: "${ROUNDTRIP_BACKUP_SERVICE:?set by the round-trip module}"

sonar_api POST /api/projects/delete --data-urlencode "project=${ROUNDTRIP_MARKER}"
echo "deleted project $ROUNDTRIP_MARKER"

if OUTPUT=$(docker compose exec -T "$ROUNDTRIP_BACKUP_SERVICE" \
      backuphelper restore "$ROUNDTRIP_SNAPSHOT_ID" --force 2>&1); then
  printf '%s\n' "$OUTPUT"
  echo "FAIL restore ran while SonarQube was running - the pre_restore gate did not refuse it" >&2
  exit 1
fi
printf '%s\n' "$OUTPUT" | sed 's/^/  | /'
# Match the raised exception itself: the traceback also prints the hook's
# source around the failing line, which contains the same text, and it may
# wrap the message across lines.
FLAT=$(tr -s '[:space:]' ' ' <<< "$OUTPUT")
if [[ "$FLAT" != *"RuntimeError: SonarQube is still running"* ]]; then
  echo "FAIL restore failed, but not because SonarQube was running (output above)" >&2
  exit 1
fi
echo "restore refused while SonarQube was running"
