# syntax=docker/dockerfile:1
# =============================================================================
# SonarQube Community Build — BAUER GROUP Edition
# =============================================================================
# Sovereign re-publish of the upstream SonarQube Community Build with the
# Community Branch Plugin baked in. Published as
# ghcr.io/bauer-group/XPD-SonarQube/sonarqube.
#
# Versions are PINNED here as the source of truth (visible + reproducible):
#   SONARQUBE_VERSION      — base image tag (…-community)
#   BRANCH_PLUGIN_VERSION  — Community Branch Plugin release (MAJOR.MINOR must
#                            equal SonarQube's; a mismatch stops SonarQube)
#
# CI keeps the pinned pair current automatically: the resolve-versions job in
# .github/workflows/docker-release.yml passes the newest plugin-compatible pair
# as --build-arg, and the daily base-image monitor watches the floating
# `sonarqube:community` tag for drift. No manual maintenance, yet every build is
# reproducible from explicit versions.
#
# Upstream:
#   Image:  https://hub.docker.com/_/sonarqube
#   Plugin: https://github.com/mc1arke/sonarqube-community-branch-plugin
# =============================================================================

ARG SONARQUBE_VERSION=26.5.0.122743-community
ARG BRANCH_PLUGIN_VERSION=26.5.0


# ── Stage 1: fetch & verify the Community Branch Plugin ──────────────────────
FROM alpine:3.22 AS plugin

ARG BRANCH_PLUGIN_VERSION
# Optional supply-chain check: pass the JAR's sha256 to verify the download.
ARG BRANCH_PLUGIN_SHA256=

RUN apk add --no-cache curl

RUN set -eux; \
    url="https://github.com/mc1arke/sonarqube-community-branch-plugin/releases/download/${BRANCH_PLUGIN_VERSION}/sonarqube-community-branch-plugin-${BRANCH_PLUGIN_VERSION}.jar"; \
    curl --proto "=https" --fail --location --silent --show-error --output /plugin.jar "${url}"; \
    if [ -n "${BRANCH_PLUGIN_SHA256}" ]; then \
        echo "${BRANCH_PLUGIN_SHA256}  /plugin.jar" | sha256sum -c -; \
    fi


# ── Stage 2: final image ─────────────────────────────────────────────────────
FROM sonarqube:${SONARQUBE_VERSION}

# Re-declare ARGs after FROM so they're usable in COPY / ENV / LABEL below.
ARG SONARQUBE_VERSION
ARG BRANCH_PLUGIN_VERSION

# Bring the verified plugin into the extensions dir. The upstream image runs as
# uid 1000 with primary group root (gid 0, the OpenShift "arbitrary UID"
# pattern) — there is no `sonarqube` group, so own it sonarqube:0.
COPY --from=plugin --chown=sonarqube:0 /plugin.jar \
     /opt/sonarqube/extensions/plugins/sonarqube-community-branch-plugin-${BRANCH_PLUGIN_VERSION}.jar

# Activate the plugin as a -javaagent in BOTH the Web and Compute Engine JVMs.
# Baked into image ENV so they always match the bundled JAR. Keep separate from
# the heap opts (SONAR_WEB_JAVAOPTS etc.).
ENV SONAR_WEB_JAVAADDITIONALOPTS="-javaagent:./extensions/plugins/sonarqube-community-branch-plugin-${BRANCH_PLUGIN_VERSION}.jar=web"
ENV SONAR_CE_JAVAADDITIONALOPTS="-javaagent:./extensions/plugins/sonarqube-community-branch-plugin-${BRANCH_PLUGIN_VERSION}.jar=ce"


# ── OCI / BAUER GROUP labels ────────────────────────────────────────────────
# image.version is the wrapper's own release version (semver) and is kept
# current automatically by CI (update-dockerfile-version → committed back), so
# the code version is always readable here without guessing. image.revision /
# image.created are additionally injected by the CI build action. The SonarQube
# and plugin versions live in base.name + the com.bauer-group.* labels.
LABEL org.opencontainers.image.version="1.0.7" \
      org.opencontainers.image.title="SonarQube Community Build" \
      org.opencontainers.image.description="SonarQube Community Build with Community Branch Plugin (BAUER GROUP Edition)" \
      org.opencontainers.image.vendor="BAUER GROUP" \
      org.opencontainers.image.authors="Karl Bauer <karl.bauer@bauer-group.com>" \
      org.opencontainers.image.licenses="LGPL-3.0-only" \
      org.opencontainers.image.source="https://github.com/bauer-group/XPD-SonarQube" \
      org.opencontainers.image.url="https://github.com/bauer-group/XPD-SonarQube" \
      org.opencontainers.image.documentation="https://github.com/bauer-group/XPD-SonarQube#readme" \
      org.opencontainers.image.base.name="docker.io/library/sonarqube:${SONARQUBE_VERSION}" \
      com.bauer-group.image.component="application" \
      com.bauer-group.image.stack="sonarqube" \
      com.bauer-group.sonarqube.version="${SONARQUBE_VERSION}" \
      com.bauer-group.branch-plugin.version="${BRANCH_PLUGIN_VERSION}"


# Inherit ENTRYPOINT, CMD, EXPOSE, HEALTHCHECK, USER (sonarqube), WORKDIR from upstream.
