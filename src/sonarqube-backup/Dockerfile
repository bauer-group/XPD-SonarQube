# =============================================================================
# SonarQube Database Backup Sidecar — BAUER GROUP
# =============================================================================
# Scheduled pg_dump of the SonarQube PostgreSQL database into a tar.gz with an
# integrity manifest, optional off-site S3 upload, count-based retention and
# multi-channel alerting (e-mail / webhook / Teams).
#
# Published as ghcr.io/bauer-group/XPD-SonarQube/sonarqube-backup.
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

# OCI / BAUER GROUP labels
LABEL org.opencontainers.image.title="SonarQube Backup Sidecar"
LABEL org.opencontainers.image.description="Scheduled PostgreSQL backup for the SonarQube stack (BAUER GROUP Edition)"
LABEL org.opencontainers.image.vendor="BAUER GROUP"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/bauer-group/XPD-SonarQube"
LABEL com.bauer-group.image.component="backup"
LABEL com.bauer-group.image.stack="sonarqube"

# Default: run the scheduler. Override with `--now`, `list`, `verify`, `restore`.
ENTRYPOINT ["python", "-m", "src.main"]
