"""Archive bundling: tar.gz of the dump plus an integrity manifest."""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path

MANIFEST_NAME = "manifest.json"
_CHUNK = 1024 * 1024


def sha256_file(path: Path) -> str:
    """Streaming SHA-256 so we never load a multi-GB dump into memory."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(
    *,
    instance: str,
    created_at: str,
    dump_format: str,
    dump_name: str,
    dump_sha256: str,
    dump_bytes: int,
) -> dict:
    return {
        "schema": 1,
        "tool": "sonarqube-backup",
        "instance": instance,
        "created_at": created_at,
        "database": {
            "format": dump_format,
            "file": dump_name,
            "sha256": dump_sha256,
            "bytes": dump_bytes,
        },
    }


def create_archive(dump_path: Path, manifest: dict, dest: Path) -> Path:
    """Bundle the dump file + manifest.json into a single .tar.gz at `dest`."""
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    with tarfile.open(dest, "w:gz") as tar:
        tar.add(dump_path, arcname=manifest["database"]["file"])
        info = tarfile.TarInfo(MANIFEST_NAME)
        info.size = len(manifest_bytes)
        import io
        tar.addfile(info, io.BytesIO(manifest_bytes))
    return dest


def read_manifest(archive: Path) -> dict:
    """Read manifest.json out of an archive without extracting the dump."""
    with tarfile.open(archive, "r:gz") as tar:
        member = tar.extractfile(MANIFEST_NAME)
        if member is None:
            raise ValueError(f"{archive.name}: no {MANIFEST_NAME}")
        return json.loads(member.read().decode("utf-8"))


def verify_archive(archive: Path) -> bool:
    """Re-hash the dump member and compare against the manifest. True if intact."""
    manifest = read_manifest(archive)
    expected = manifest["database"]["sha256"]
    dump_name = manifest["database"]["file"]
    h = hashlib.sha256()
    with tarfile.open(archive, "r:gz") as tar:
        member = tar.extractfile(dump_name)
        if member is None:
            return False
        for chunk in iter(lambda: member.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest() == expected
