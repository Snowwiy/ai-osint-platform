from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.services.knowledge.document_metadata import build_file_metadata

_SUPPORTED_SUFFIXES = {".md", ".txt"}
_IGNORED_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__"}
_MAX_FILE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class LoadedDocument:
    path: Path
    source_type: str
    content: str
    file_hash: str
    created_at: datetime
    updated_at: datetime


def load_documents_from_paths(
    paths: Sequence[str | Path],
    *,
    source_type: str,
) -> list[LoadedDocument]:
    documents: list[LoadedDocument] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            continue
        if path.is_file():
            loaded = _load_file(path, source_type)
            if loaded is not None:
                documents.append(loaded)
            continue
        documents.extend(_load_directory(path, source_type))
    return sorted(
        documents, key=lambda document: (document.path.name, str(document.path))
    )


def _load_directory(path: Path, source_type: str) -> list[LoadedDocument]:
    documents: list[LoadedDocument] = []
    for child in path.rglob("*"):
        if _is_ignored(child):
            continue
        loaded = _load_file(child, source_type)
        if loaded is not None:
            documents.append(loaded)
    return documents


def _load_file(path: Path, source_type: str) -> LoadedDocument | None:
    if not path.is_file() or path.suffix.lower() not in _SUPPORTED_SUFFIXES:
        return None
    if _is_ignored(path) or path.stat().st_size > _MAX_FILE_BYTES:
        return None
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    metadata = build_file_metadata(path, content)
    return LoadedDocument(
        path=path,
        source_type=source_type,
        content=content,
        file_hash=metadata.file_hash,
        created_at=metadata.created_at,
        updated_at=metadata.updated_at,
    )


def _is_ignored(path: Path) -> bool:
    return any(part in _IGNORED_DIRS for part in path.parts)
