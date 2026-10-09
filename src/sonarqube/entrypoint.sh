#!/bin/bash
# =============================================================================
# SonarQube wrapper entrypoint — installs the bundled plugins on every start
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

exec /opt/sonarqube/docker/entrypoint.sh "$@"
