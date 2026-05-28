from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class FileMetadata:
    file_path: Path
    file_hash: str
    created_at: datetime
    updated_at: datetime


def build_file_metadata(path: Path, content: str) -> FileMetadata:
    stat = path.stat()
    return FileMetadata(
        file_path=path,
        file_hash=hash_content(content),
        created_at=datetime.fromtimestamp(stat.st_ctime, tz=UTC),
        updated_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
    )


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
