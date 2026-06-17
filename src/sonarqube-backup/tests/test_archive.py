import hashlib
import tarfile

from src import archive


def _make_dump(tmp_path, content=b"PGDMP fake dump payload"):
    dump = tmp_path / "database.dump"
    dump.write_bytes(content)
    return dump


def test_sha256_file_matches_hashlib(tmp_path):
    dump = _make_dump(tmp_path)
    assert archive.sha256_file(dump) == hashlib.sha256(dump.read_bytes()).hexdigest()


def test_create_and_verify_roundtrip(tmp_path):
    dump = _make_dump(tmp_path)
    manifest = archive.build_manifest(
        instance="sonarqube",
        created_at="2026-06-17T03:15:00+00:00",
        dump_format="custom",
        dump_name="database.dump",
        dump_sha256=archive.sha256_file(dump),
        dump_bytes=dump.stat().st_size,
    )
    dest = tmp_path / "sonarqube-20260617-031500.tar.gz"
    archive.create_archive(dump, manifest, dest)

    assert dest.exists()
    read = archive.read_manifest(dest)
    assert read["database"]["file"] == "database.dump"
    assert read["instance"] == "sonarqube"
    assert archive.verify_archive(dest) is True


def test_verify_detects_tampered_manifest(tmp_path):
    dump = _make_dump(tmp_path)
    # Manifest claims a wrong hash → verify must fail.
    manifest = archive.build_manifest(
        instance="sonarqube",
        created_at="2026-06-17T03:15:00+00:00",
        dump_format="custom",
        dump_name="database.dump",
        dump_sha256="0" * 64,
        dump_bytes=dump.stat().st_size,
    )
    dest = tmp_path / "bad.tar.gz"
    archive.create_archive(dump, manifest, dest)
    assert archive.verify_archive(dest) is False


def test_archive_contains_manifest_member(tmp_path):
    dump = _make_dump(tmp_path)
    manifest = archive.build_manifest(
        instance="x", created_at="t", dump_format="plain",
        dump_name="database.dump", dump_sha256=archive.sha256_file(dump),
        dump_bytes=dump.stat().st_size,
    )
    dest = tmp_path / "a.tar.gz"
    archive.create_archive(dump, manifest, dest)
    with tarfile.open(dest, "r:gz") as tar:
        names = tar.getnames()
    assert archive.MANIFEST_NAME in names
    assert "database.dump" in names
