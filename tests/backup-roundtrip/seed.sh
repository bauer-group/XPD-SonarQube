#!/usr/bin/env bash
# =============================================================================
# XPD-SonarQube backup round trip - seed
# =============================================================================
# Creates, through the SonarQube web API, a project whose key and name are the
# run's marker. SonarQube writes it to PostgreSQL (the "sonar" component of the
# snapshot) and indexes it in Elasticsearch for the Projects page.
# =============================================================================
set -euo pipefail
# shellcheck source=tests/backup-roundtrip/common.sh
source "$(dirname "$0")/common.sh"

sonar_api POST /api/projects/create \
  --data-urlencode "project=${ROUNDTRIP_MARKER}" \
  --data-urlencode "name=${ROUNDTRIP_MARKER}" > /dev/null

echo "seeded project $ROUNDTRIP_MARKER"
