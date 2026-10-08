#!/usr/bin/env bash
# =============================================================================
# XPD-SonarQube backup round trip - mutate
# =============================================================================
# Deletes the seeded project the way a user does: through the SonarQube web
# API, which removes it from PostgreSQL and from the search index. The restore
# has to bring it back in both.
# =============================================================================
set -euo pipefail
# shellcheck source=tests/backup-roundtrip/common.sh
source "$(dirname "$0")/common.sh"

sonar_api POST /api/projects/delete --data-urlencode "project=${ROUNDTRIP_MARKER}"

echo "deleted project $ROUNDTRIP_MARKER"
