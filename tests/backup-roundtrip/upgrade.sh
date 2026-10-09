#!/usr/bin/env bash
# =============================================================================
# XPD-SonarQube backup round trip - upgrade
# =============================================================================
# The module's upgrade-script: runs once, against the running previous release,
# right before the stack switches to the images built from this commit.
#
# An upgrade asks the operator for one thing (docs/upgrade.md): when the new
# SonarQube finds an older database schema, it waits in DB_MIGRATION_NEEDED -
# not UP, so not healthy - until someone opens /setup and starts the migration.
# The new SonarQube only asks once it runs, and the module's 'up --wait' blocks
# until it is healthy. So this script hands the step to migrate-db.sh, started
# in the background in a session of its own: it outlives this script, watches
# the sonarqube container for the rest of the job and starts the migration
# whenever SonarQube asks - at the upgrade, and again after the restore, which
# puts the previous release's schema back. The runner stops it when the job
# ends. Its log goes to the diagnostics artifact.
#
# Between two releases on the same SonarQube version nothing asks, and the
# watcher only logs the status.
#
# Before that, it gives the previous release the plugin state a SonarQube bump
# leaves behind. The upstream image declares /opt/sonarqube/extensions a
# volume, and Compose hands that anonymous volume to the recreated container,
# so after an upgrade the new image finds the previous release's branch
# plugin there. Between two releases on the same SonarQube the JAR names
# match and nothing shows; on a real bump the new -javaagent JAR is missing
# and SonarQube does not start. So the previous release's JAR is renamed to a
# version no image ships: the new image has to install its own plugin again
# and drop the old one (src/sonarqube/entrypoint.sh), or the upgrade fails.
# =============================================================================
set -euo pipefail
: "${COMPOSE_PROJECT_NAME:?set by the round-trip module}"

docker compose exec -T sonarqube sh -c '
  cd "${SQ_EXTENSIONS_DIR:-/opt/sonarqube/extensions}/plugins"
  n=0
  for jar in sonarqube-community-branch-plugin-*.jar; do
    [ -e "$jar" ] || continue
    mv "$jar" "sonarqube-community-branch-plugin-0.0.$n.jar"
    echo "previous release: $jar renamed to sonarqube-community-branch-plugin-0.0.$n.jar"
    n=$((n + 1))
  done
  [ "$n" -gt 0 ] || echo "previous release: no branch plugin in extensions/plugins"'

LOG_DIR="${ROUNDTRIP_DIR:-${RUNNER_TEMP:?}/backup-roundtrip}/diagnostics"
mkdir -p "$LOG_DIR"
setsid bash "$(dirname "$0")/migrate-db.sh" "$COMPOSE_PROJECT_NAME" \
  > "$LOG_DIR/sonarqube-migrate-db.log" 2>&1 < /dev/null &
echo "database migration watcher started (pid $!), log: sonarqube-migrate-db.log in the diagnostics"
