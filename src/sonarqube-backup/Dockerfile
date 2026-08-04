# =============================================================================
# SonarQube Database Backup — meta image on the central BackupHelper engine
# =============================================================================
# Thin wrapper: FROM the central BackupHelper engine + SonarQube-specific OCI
# labels. All backup logic (pg_dump, retention, manifest, S3, notifications,
# restore CLI) lives in ghcr.io/bauer-group/cs-backuphelper/backuphelper, which
# already ships the postgres/mariadb clients, a non-root user, tini and a
# functional healthcheck. See docs/migration.md in that repo.
# =============================================================================
FROM ghcr.io/bauer-group/cs-backuphelper/backuphelper:latest

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
LABEL org.opencontainers.image.version="1.3.2"
LABEL com.bauer-group.image.component="backup"
LABEL com.bauer-group.image.stack="sonarqube"

# Inherit ENTRYPOINT, USER, ENV, HEALTHCHECK from the base image.
