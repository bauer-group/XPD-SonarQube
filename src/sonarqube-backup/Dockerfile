# =============================================================================
# SonarQube Database Backup — meta image on the central BackupHelper engine
# =============================================================================
# Thin wrapper: FROM the central BackupHelper engine + SonarQube-specific OCI
# labels + one restore hook. All backup logic (pg_dump, retention, manifest, S3,
# notifications, restore CLI) lives in ghcr.io/bauer-group/cs-backuphelper/backuphelper,
# which already ships the postgres/mariadb clients, a non-root user, tini and a
# functional healthcheck. See docs/migration.md in that repo.
#
# The SonarQube-specific part is the `sonarqube_backup_ext` plugin (./plugin):
# a post_restore hook that drops SonarQube's search indexes (data/es8) after a
# database restore, so SonarQube rebuilds them from the restored database. The
# engine discovers it via the backuphelper.hooks entry point.
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Test — the plugin tests gate the image build
# -----------------------------------------------------------------------------
FROM ghcr.io/bauer-group/cs-backuphelper/backuphelper:latest AS test

USER root
COPY plugin /opt/backuphelper-sonarqube
RUN pip install --no-cache-dir "/opt/backuphelper-sonarqube[test]" \
    && python -m pytest /opt/backuphelper-sonarqube/tests -q -p no:cacheprovider

# -----------------------------------------------------------------------------
# Stage 2: Production — engine + plugin
# -----------------------------------------------------------------------------
FROM ghcr.io/bauer-group/cs-backuphelper/backuphelper:latest

USER root
COPY plugin /opt/backuphelper-sonarqube
RUN pip install --no-cache-dir /opt/backuphelper-sonarqube \
    && rm -rf /opt/backuphelper-sonarqube

# Fail the build unless the test stage passed (creates a dependency on it).
COPY --from=test /opt/backuphelper-sonarqube/pyproject.toml /tmp/plugin-tests-passed
RUN rm -f /tmp/plugin-tests-passed

# ---------------------------------------------------------------------------
# Metadata Labels
# ---------------------------------------------------------------------------
LABEL vendor="BAUER GROUP"
LABEL maintainer="Karl Bauer <karl.bauer@bauer-group.com>"

LABEL org.opencontainers.image.title="SonarQube Backup Sidecar"
LABEL org.opencontainers.image.description="Scheduled PostgreSQL backup for the SonarQube stack (BAUER GROUP Edition)"
LABEL org.opencontainers.image.vendor="BAUER GROUP"
LABEL org.opencontainers.image.authors="Karl Bauer <karl.bauer@bauer-group.com>"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/bauer-group/XPD-SonarQube"
LABEL org.opencontainers.image.url="https://github.com/bauer-group/XPD-SonarQube"
LABEL org.opencontainers.image.documentation="https://github.com/bauer-group/XPD-SonarQube/blob/main/src/sonarqube-backup/README.md"
LABEL org.opencontainers.image.version="1.3.15"
LABEL com.bauer-group.image.component="backup"
LABEL com.bauer-group.image.stack="sonarqube"

# Drop back to the engine's non-root user (uid 1000, the same uid SonarQube
# runs as, so it may empty the index directories); inherit ENTRYPOINT, ENV and
# HEALTHCHECK from the base image.
USER backup
