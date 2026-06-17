# =============================================================================
# SonarQube Database Backup Sidecar — BAUER GROUP
# =============================================================================
# Scheduled pg_dump of the SonarQube PostgreSQL database into a tar.gz with an
# integrity manifest, optional off-site S3 upload, count-based retention and
# multi-channel alerting (e-mail / webhook / Teams).
#
# Published as ghcr.io/bauer-group/xpd-sonarqube/sonarqube-backup.
# =============================================================================

FROM python:3.14-alpine

# pg_dump / pg_restore / psql. The client MAJOR must be >= the PostgreSQL
# server MAJOR — keep PG_MAJOR in step with POSTGRES_VERSION in .env (18).
ARG PG_MAJOR=18

RUN apk add --no-cache "postgresql${PG_MAJOR}-client" tzdata

WORKDIR /app

COPY requirements.txt requirements-test.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pytest.ini ./
COPY src/ ./src/
COPY tests/ ./tests/

# Test-gated build: the unit tests must pass, or the image fails to build.
RUN pip install --no-cache-dir -r requirements-test.txt \
 && python -m pytest \
 && pip uninstall -y pytest

# Run as a non-root user; /data holds the local archives.
RUN adduser -D -u 1000 backup \
 && mkdir -p /data \
 && chown -R backup:backup /data /app
USER backup

VOLUME ["/data"]

# OCI / BAUER GROUP labels — image.version (code/release version) is kept
# current by CI (update-dockerfile-version → committed back); image.revision /
# image.created are injected by the build action.
LABEL org.opencontainers.image.version="1.2.1" \
      org.opencontainers.image.title="SonarQube Backup Sidecar" \
      org.opencontainers.image.description="Scheduled PostgreSQL backup for the SonarQube stack (BAUER GROUP Edition)" \
      org.opencontainers.image.vendor="BAUER GROUP" \
      org.opencontainers.image.authors="Karl Bauer <karl.bauer@bauer-group.com>" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/bauer-group/XPD-SonarQube" \
      org.opencontainers.image.url="https://github.com/bauer-group/XPD-SonarQube" \
      org.opencontainers.image.documentation="https://github.com/bauer-group/XPD-SonarQube/blob/main/src/sonarqube-backup/README.md" \
      org.opencontainers.image.base.name="docker.io/library/python:3.14-alpine" \
      com.bauer-group.image.component="backup" \
      com.bauer-group.image.stack="sonarqube"

# Default: run the scheduler. Override with `--now`, `list`, `verify`, `restore`.
ENTRYPOINT ["python", "-m", "src.main"]
