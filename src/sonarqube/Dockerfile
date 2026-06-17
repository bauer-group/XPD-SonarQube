# =============================================================================
# SonarQube Community Build — BAUER GROUP Edition
# =============================================================================
# Sovereign re-publish of the upstream SonarQube Community Build image with the
# Community Branch Plugin baked in. We rebuild under BAUER GROUP control
# (ghcr.io/bauer-group/XPD-SonarQube/sonarqube) so branch/PR analysis is
# reproducible from CI and pinned to a known-compatible plugin version, instead
# of being hand-installed via the Marketplace at runtime.
#
# Why bake the plugin in (not a persisted extensions/ volume):
#   The plugin is version-locked to SonarQube (plugin MAJOR.MINOR must equal the
#   SonarQube MAJOR.MINOR). Shipping it in the image layer means an image bump
#   atomically upgrades BOTH — a stale named volume can never shadow a newer
#   plugin. Consequence: do NOT mount a named volume over /opt/sonarqube/extensions
#   in the compose files (see docs/branch-analysis.md).
#
# Version pinning (bump as a PAIR — see docs/upgrade.md):
#   SONARQUBE_VERSION      26.5.0.122743-community   (Docker Hub: library/sonarqube)
#   BRANCH_PLUGIN_VERSION  26.5.0                     (github.com/mc1arke/sonarqube-community-branch-plugin)
#
# CAUTION: do NOT default SONARQUBE_VERSION to `community`/`latest`. The floating
# tag races ahead of the plugin (e.g. SonarQube 26.6 exists before plugin 26.6),
# and a version-mismatched plugin refuses to load — SonarQube then fails to start.
#
# Upstream sources:
#   - Image:  https://hub.docker.com/_/sonarqube
#   - Code:   https://github.com/SonarSource/sonarqube
#   - Docs:   https://docs.sonarsource.com/sonarqube-community-build/
#   - Plugin: https://github.com/mc1arke/sonarqube-community-branch-plugin
# =============================================================================


# ── Build Arguments (Base Image) ────────────────────────────────────────────
# Override at build time to track a different Community Build / plugin pair:
#   docker build \
#     --build-arg SONARQUBE_VERSION=26.6.0.123539-community \
#     --build-arg BRANCH_PLUGIN_VERSION=26.6.0 \
#     -t sonarqube-bauer:test ./src/sonarqube
ARG SONARQUBE_VERSION=26.5.0.122743-community

FROM sonarqube:${SONARQUBE_VERSION}

# Re-declare ARGs after FROM so they're available below.
ARG SONARQUBE_VERSION
ARG BRANCH_PLUGIN_VERSION=26.5.0
# Optional supply-chain check: pass the JAR's sha256 to verify the download.
# Leave empty to skip (e.g. local builds). Set in CI for production images.
ARG BRANCH_PLUGIN_SHA256=


# ── Community Branch Plugin ─────────────────────────────────────────────────
# Adds branch & pull-request analysis to the Community Build. The JAR doubles
# as a -javaagent for the Web and Compute Engine JVMs — those agent options are
# wired in via SONAR_WEB_JAVAADDITIONALOPTS / SONAR_CE_JAVAADDITIONALOPTS in the
# compose files (kept visible there, coupled to this exact filename/version).
USER root

ADD https://github.com/mc1arke/sonarqube-community-branch-plugin/releases/download/${BRANCH_PLUGIN_VERSION}/sonarqube-community-branch-plugin-${BRANCH_PLUGIN_VERSION}.jar \
    /opt/sonarqube/extensions/plugins/sonarqube-community-branch-plugin-${BRANCH_PLUGIN_VERSION}.jar

RUN set -eux; \
    plugin="/opt/sonarqube/extensions/plugins/sonarqube-community-branch-plugin-${BRANCH_PLUGIN_VERSION}.jar"; \
    if [ -n "${BRANCH_PLUGIN_SHA256}" ]; then \
        echo "${BRANCH_PLUGIN_SHA256}  ${plugin}" | sha256sum -c -; \
    fi; \
    # Upstream creates the sonarqube user with primary group root (gid 0,
    # the OpenShift "arbitrary UID" pattern) — there is no `sonarqube` group.
    chown sonarqube:0 "${plugin}"; \
    chmod 0644 "${plugin}"

# Activate the plugin as a -javaagent in BOTH the Web and Compute Engine JVMs.
# Baked into the image so the agent path always matches the JAR shipped above —
# they can never drift across an upgrade. The compose files deliberately do NOT
# set these (override only if you know exactly why). Note: these are *additional*
# opts and must stay separate from the heap opts (SONAR_WEB_JAVAOPTS etc.).
ENV SONAR_WEB_JAVAADDITIONALOPTS="-javaagent:./extensions/plugins/sonarqube-community-branch-plugin-${BRANCH_PLUGIN_VERSION}.jar=web"
ENV SONAR_CE_JAVAADDITIONALOPTS="-javaagent:./extensions/plugins/sonarqube-community-branch-plugin-${BRANCH_PLUGIN_VERSION}.jar=ce"

USER sonarqube


# ── OCI / BAUER GROUP labels ────────────────────────────────────────────────
LABEL vendor="BAUER GROUP"
LABEL maintainer="Karl Bauer <karl.bauer@bauer-group.com>"

LABEL org.opencontainers.image.title="SonarQube Community Build"
LABEL org.opencontainers.image.description="SonarQube Community Build with Community Branch Plugin (BAUER GROUP Edition)"
LABEL org.opencontainers.image.vendor="BAUER GROUP"
LABEL org.opencontainers.image.authors="Karl Bauer <karl.bauer@bauer-group.com>"
LABEL org.opencontainers.image.licenses="LGPL-3.0-only"
LABEL org.opencontainers.image.source="https://github.com/bauer-group/XPD-SonarQube"
LABEL org.opencontainers.image.url="https://github.com/bauer-group/XPD-SonarQube"
LABEL org.opencontainers.image.documentation="https://github.com/bauer-group/XPD-SonarQube#readme"
LABEL org.opencontainers.image.base.name="docker.io/library/sonarqube:${SONARQUBE_VERSION}"
LABEL com.bauer-group.image.component="application"
LABEL com.bauer-group.image.stack="sonarqube"
LABEL com.bauer-group.image.branch-plugin.version="${BRANCH_PLUGIN_VERSION}"


# Inherit ENTRYPOINT, CMD, EXPOSE, HEALTHCHECK, USER, WORKDIR from upstream.
