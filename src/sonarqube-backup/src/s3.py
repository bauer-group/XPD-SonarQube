"""Optional off-site S3 target — thin boto3 wrapper.

boto3 is imported lazily so the dependency is only touched when S3 is actually
configured (S3_ENDPOINT + S3_BUCKET set).
"""

from __future__ import annotations

import logging
from pathlib import Path

from .config import Config
from .retention import select_expired

log = logging.getLogger(__name__)


class S3Target:
    def __init__(self, cfg: Config) -> None:
        import boto3  # lazy

        self._cfg = cfg
        self._bucket = cfg.s3_bucket
        # Normalise to a trailing-slash prefix, or empty for bucket root.
        self._prefix = (cfg.s3_prefix.rstrip("/") + "/") if cfg.s3_prefix.strip("/") else ""
        self._client = boto3.client(
            "s3",
            endpoint_url=cfg.s3_endpoint or None,
            region_name=cfg.s3_region or None,
            aws_access_key_id=cfg.s3_access_key or None,
            aws_secret_access_key=cfg.s3_secret_key or None,
        )

    def _key(self, name: str) -> str:
        return f"{self._prefix}{name}"

    def upload(self, path: Path) -> str:
        key = self._key(path.name)
        log.info("s3: uploading %s → s3://%s/%s", path.name, self._bucket, key)
        self._client.upload_file(str(path), self._bucket, key)
        return key

    def list_archive_names(self) -> list[str]:
        """Names (basename) of *.tar.gz objects under the prefix."""
        names: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".tar.gz"):
                    names.append(key.rsplit("/", 1)[-1])
        return names

    def prune(self, keep: int) -> list[str]:
        expired = select_expired(self.list_archive_names(), keep)
        for name in expired:
            self._client.delete_object(Bucket=self._bucket, Key=self._key(name))
            log.info("retention: pruned s3 %s", name)
        return expired
