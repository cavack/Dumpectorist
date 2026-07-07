import json
from datetime import datetime, timezone
from hashlib import sha256

import pytest

from app.ops.backup import build_backup_manifest, write_backup_manifest


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def test_backup_manifest_hashes_and_writes_artifacts(tmp_path):
    first = tmp_path / "first.dump"
    second = tmp_path / "second.dump"
    first.write_bytes(b"first")
    second.write_bytes(b"second-file")

    manifest = build_backup_manifest((second, first), created_at=NOW)

    assert [artifact.name for artifact in manifest.artifacts] == [
        "first.dump",
        "second.dump",
    ]
    assert manifest.total_bytes == len(b"first") + len(b"second-file")
    assert manifest.artifacts[0].sha256 == sha256(b"first").hexdigest()

    destination = write_backup_manifest(manifest, tmp_path / "manifest.json")
    payload = json.loads(destination.read_text(encoding="utf-8"))

    assert payload["total_bytes"] == manifest.total_bytes
    assert payload["artifacts"][1]["name"] == "second.dump"
    assert not (tmp_path / "manifest.json.tmp").exists()


def test_backup_manifest_rejects_missing_file(tmp_path):
    with pytest.raises(ValueError):
        build_backup_manifest((tmp_path / "missing.dump",), created_at=NOW)


def test_backup_manifest_rejects_duplicate_files(tmp_path):
    artifact = tmp_path / "same.dump"
    artifact.write_bytes(b"data")

    with pytest.raises(ValueError):
        build_backup_manifest((artifact, artifact), created_at=NOW)


def test_backup_manifest_rejects_naive_timestamp(tmp_path):
    artifact = tmp_path / "file.dump"
    artifact.write_bytes(b"data")

    with pytest.raises(ValueError):
        build_backup_manifest(
            (artifact,),
            created_at=datetime(2026, 7, 7, 12, 0),
        )
