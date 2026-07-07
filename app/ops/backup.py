from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from app.ops.models import BackupArtifact, BackupManifest


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_backup_manifest(
    paths: Iterable[Path],
    *,
    created_at: datetime,
) -> BackupManifest:
    _require_aware(created_at)
    resolved_paths = tuple(Path(path).resolve() for path in paths)
    if not resolved_paths:
        raise ValueError("at least one backup artifact is required")
    if len(set(resolved_paths)) != len(resolved_paths):
        raise ValueError("backup artifacts must be unique")

    artifacts: list[BackupArtifact] = []
    for path in sorted(resolved_paths, key=lambda item: item.name):
        if not path.is_file():
            raise ValueError(f"backup artifact is not a file: {path.name}")
        artifacts.append(
            BackupArtifact(
                name=path.name,
                size_bytes=path.stat().st_size,
                sha256=_file_sha256(path),
            )
        )

    return BackupManifest(
        created_at=created_at,
        total_bytes=sum(item.size_bytes for item in artifacts),
        artifacts=tuple(artifacts),
    )


def write_backup_manifest(manifest: BackupManifest, destination: Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(destination)
    return destination
