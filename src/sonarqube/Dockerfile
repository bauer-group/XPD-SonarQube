# =============================================================================
# SonarQube Community Build — BAUER GROUP Edition
# =============================================================================
# Sovereign re-publish of the upstream SonarQube Community Build image with the
# Community Branch Plugin baked in, published as
# ghcr.io/bauer-group/XPD-SonarQube/sonarqube.
#
# FLOATING by design — no hard-coded version anywhere:
#   * The base floats on the `community` tag (latest Community Build), so the
#     daily base-image monitor catches digest drift and triggers a rebuild,
#     keeping the image current with upstream security fixes automatically.
#   * The Community Branch Plugin is version-locked to SonarQube. Instead of
#     pinning it, this Dockerfile RESOLVES it at build time from the base
#     image's own $SONAR_VERSION (plugin tag = <MAJOR>.<MINOR>.0) and stores it
#     under a version-less filename, so the -javaagent ENV below never has to
#     change.
#
# Because `community` can briefly run ahead of the plugin's releases, CI passes
# a resolved, plugin-compatible `SONARQUBE_VERSION` via --build-arg (see the
# resolve-versions job in .github/workflows/docker-release.yml). That keeps the
# published image green and always on the newest WORKING pair. A bare
# `docker build` with no build-arg uses `community` and will fail only during a
# short window when the plugin has not yet released for a brand-new SonarQube —
# the previously published image keeps running until then.
#
# Upstream:
#   Image:  https://hub.docker.com/_/sonarqube
#   Plugin: https://github.com/mc1arke/sonarqube-community-branch-plugin
# =============================================================================

ARG SONARQUBE_VERSION=community

FROM sonarqube:${SONARQUBE_VERSION}

# ── Community Branch Plugin (resolved from the base image's version) ─────────
# Adds branch & pull-request analysis to the Community Build. The JAR doubles as
# a -javaagent for the Web and Compute Engine JVMs (wired via ENV below).
USER root

RUN set -eux; \
    # The base image exposes its exact version as $SONAR_VERSION (e.g. 26.5.0.122743).
    minor="$(printf '%s' "${SONAR_VERSION}" | cut -d. -f1-2)"; \
    plugin_tag="${minor}.0"; \
    echo "Resolving branch plugin for SonarQube ${SONAR_VERSION} -> plugin ${plugin_tag}"; \
    dest="/opt/sonarqube/extensions/plugins/sonarqube-community-branch-plugin.jar"; \
    curl --proto "=https" --fail --location --silent --show-error \
        "https://github.com/mc1arke/sonarqube-community-branch-plugin/releases/download/${plugin_tag}/sonarqube-community-branch-plugin-${plugin_tag}.jar" \
        --output "${dest}"; \
    # Upstream creates the sonarqube user with primary group root (gid 0,
    # the OpenShift "arbitrary UID" pattern) — there is no `sonarqube` group.
    chown sonarqube:0 "${dest}"; \
    chmod 0644 "${dest}"

USER sonarqube

# Activate the plugin as a -javaagent in BOTH JVMs. The version-less filename
# keeps these static no matter which SonarQube/plugin version was resolved.
# Keep separate from the heap opts (SONAR_WEB_JAVAOPTS etc.).
ENV SONAR_WEB_JAVAADDITIONALOPTS="-javaagent:./extensions/plugins/sonarqube-community-branch-plugin.jar=web"
ENV SONAR_CE_JAVAADDITIONALOPTS="-javaagent:./extensions/plugins/sonarqube-community-branch-plugin.jar=ce"


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
LABEL com.bauer-group.image.component="application"
LABEL com.bauer-group.image.stack="sonarqube"


# Inherit ENTRYPOINT, CMD, EXPOSE, HEALTHCHECK, USER, WORKDIR from upstream.
