from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import re
import shutil
import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.models.knowledge_link import KnowledgeLink
from app.models.knowledge_source import KnowledgeSource
from app.services.audit import record_event
from app.services.knowledge.document_chunker import chunk_document
from app.services.knowledge.ingestion import (
    DocumentParseError,
    ParsedFile,
    scan_directory,
)

_TRUST = {"authoritative", "trusted", "internal", "community", "unknown"}
_VERIFICATION = {"verified", "reviewed", "unverified", "stale", "rejected"}
_SOURCE_TYPES = {"obsidian_vault", "document_upload", "manual_reference"}
_URL_RE = re.compile(r"^https?://[^\s]{1,990}$", re.IGNORECASE)
_SOURCE_MARKER = ".raventech-knowledge-source.json"


def import_root() -> Path:
    base = (
        Path(settings.CHROMA_DATA_PATH).expanduser().parent / "knowledge_imports"
    ).resolve()
    base.mkdir(parents=True, exist_ok=True)
    try:
        base.chmod(0o700)
    except OSError:
        pass
    return base


def validate_source_metadata(
    *,
    source_type: str,
    trust_level: str,
    verification_status: str,
    canonical_url: str | None,
) -> None:
    if source_type not in _SOURCE_TYPES:
        raise ValueError("Unsupported Knowledge source type.")
    if trust_level not in _TRUST or verification_status not in _VERIFICATION:
        raise ValueError("Invalid source trust or verification value.")
    if canonical_url and not _URL_RE.fullmatch(canonical_url.strip()):
        raise ValueError("Canonical reference must be an HTTP(S) URL.")


def _safe_relative_name(value: str) -> str | None:
    normalized = value.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or ":" in path.parts[0]
        or len(normalized) > 1000
    ):
        raise ValueError("Selected document path is unsafe.")
    if any(
        part.casefold()
        in {
            ".obsidian",
            ".git",
            "node_modules",
            "venv",
            ".venv",
            "__pycache__",
            "tmp",
            "cache",
        }
        for part in path.parts
    ):
        return None
    if any(part.casefold() == _SOURCE_MARKER.casefold() for part in path.parts):
        raise ValueError("Selected document path is reserved by RavenTech.")
    return path.as_posix()


async def create_uploaded_source(
    db: AsyncSession,
    *,
    name: str,
    source_type: str,
    files: list[tuple[str, bytes, int]],
    trust_level: str = "unknown",
    verification_status: str = "unverified",
    publisher: str | None = None,
    canonical_url: str | None = None,
    publication_date: str | None = None,
    version_label: str | None = None,
    notes: str | None = None,
    language: str | None = None,
    category: str = "Other",
    local_root_path: str | None = None,
) -> KnowledgeSource:
    validate_source_metadata(
        source_type=source_type,
        trust_level=trust_level,
        verification_status=verification_status,
        canonical_url=canonical_url,
    )
    clean_name = " ".join(name.strip().split())[:200]
    if not clean_name or not files:
        raise ValueError("A source name and at least one selected file are required.")
    if local_root_path and source_type != "obsidian_vault":
        raise ValueError("Only an Obsidian vault can retain a local source location.")
    canonical_local_root = (
        validate_local_vault_root(local_root_path) if local_root_path else None
    )
    if len(files) > settings.KNOWLEDGE_MAX_UPLOAD_FILES:
        raise ValueError("Selected file count exceeds the configured limit.")
    total = sum(len(data) for _, data, _ in files)
    if total > settings.KNOWLEDGE_MAX_UPLOAD_BYTES:
        raise ValueError("Selected files exceed the configured upload limit.")
    source = KnowledgeSource(
        name=clean_name,
        source_type=source_type,
        local_root_path=canonical_local_root,
        display_location=f"Selected {source_type.replace('_', ' ')}: {clean_name}",
        category=_clean(category, 80) or "Other",
        platform=platform.system().lower()[:20],
        status="pending",
        trust_level=trust_level,
        verification_status=verification_status,
        publisher=_clean(publisher, 200),
        canonical_url=canonical_url.strip() if canonical_url else None,
        publication_date=_clean(publication_date, 40),
        version_label=_clean(version_label, 120),
        notes=_clean(notes, 2000),
        language=_clean(language, 16),
        metadata_json={},
    )
    db.add(source)
    await db.flush()
    root = import_root() / str(source.id)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    try:
        (root / _SOURCE_MARKER).write_text(
            json.dumps({"source_id": str(source.id), "source_type": source_type}),
            encoding="utf-8",
        )
        source.root_path = str(root)
        selected = await _write_uploaded_files(root, files)
    except Exception:
        # This directory was created in this call and is removed only when its
        # RavenTech ownership marker still proves it is the expected snapshot.
        try:
            if _validated_snapshot_root(source) == root.resolve(strict=True):
                shutil.rmtree(root)
        except (DocumentParseError, OSError):
            pass
        raise
    source.metadata_json = {"selected_paths": sorted(set(selected))}
    await db.flush()
    return source


async def update_uploaded_source_files(
    source: KnowledgeSource,
    files: list[tuple[str, bytes, int]],
) -> list[str]:
    if not files:
        raise ValueError("Select at least one supported document.")
    if not source.root_path or source.source_type not in _SOURCE_TYPES:
        raise ValueError("This Knowledge source cannot accept local document uploads.")
    try:
        root = _validated_snapshot_root(source)
    except DocumentParseError:
        raise ValueError("Knowledge source storage boundary is invalid.") from None
    return await _write_uploaded_files(root, files, allow_replace=True)


async def _write_uploaded_files(
    root: Path,
    files: list[tuple[str, bytes, int]],
    *,
    allow_replace: bool = False,
) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    total = sum(len(data) for _, data, _ in files)
    if (
        len(files) > settings.KNOWLEDGE_MAX_UPLOAD_FILES
        or total > settings.KNOWLEDGE_MAX_UPLOAD_BYTES
    ):
        raise ValueError("Selected files exceed the configured upload limit.")
    for raw_name, data, modified_ns in files:
        relative = _safe_relative_name(raw_name)
        if relative is None:
            continue
        if relative in seen:
            raise ValueError("Duplicate document names are not accepted in one import.")
        seen.add(relative)
        target = root.joinpath(*PurePosixPath(relative).parts)
        resolved_root = root.resolve(strict=True)
        current_parent = resolved_root
        for part in PurePosixPath(relative).parts[:-1]:
            next_parent = current_parent / part
            if _is_local_link(next_parent):
                raise ValueError("Selected document path crosses an unsafe link.")
            if not next_parent.exists():
                next_parent.mkdir(mode=0o700)
            elif not next_parent.is_dir():
                raise ValueError("Selected document parent is not a directory.")
            current_parent = next_parent.resolve(strict=True)
            if not current_parent.is_relative_to(resolved_root):
                raise ValueError("Selected document path escapes the source boundary.")
        if _is_local_link(target) or target.exists() and not allow_replace:
            raise ValueError("Duplicate document names are not accepted in one import.")
        if target.exists() and not target.is_file():
            raise ValueError("Selected document target is not a regular file.")
        staging = target.with_name(f".{target.name}.{uuid.uuid4().hex}.upload")
        staging.write_bytes(data)
        os.replace(staging, target)
        os.utime(target, ns=(modified_ns, modified_ns))
        selected.append(relative)
    return selected


async def sync_knowledge_source(
    db: AsyncSession, source_id: uuid.UUID
) -> dict[str, Any]:
    source = (
        await db.execute(
            select(KnowledgeSource)
            .where(KnowledgeSource.id == source_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if source is None or source.status == "disabled":
        raise ValueError("Knowledge source is unavailable or disabled.")
    if source.local_root_path:
        try:
            source_root = _resolve_local_vault_root(source.local_root_path)
        except DocumentParseError as exc:
            if exc.code == "source_offline":
                source.status = "offline"
                source.availability = "offline"
                source.error_summary = (
                    "Selected vault is offline. Indexed documents were preserved; "
                    "relink it when available."
                )
                return {
                    "indexed": 0,
                    "unchanged": 0,
                    "failed": 0,
                    "deleted": 0,
                    "offline": True,
                }
            source.status = "failed"
            source.availability = "unsafe"
            source.error_summary = (
                "Selected vault failed a local path safety check. Indexed "
                "documents were preserved."
            )
            return {
                "indexed": 0,
                "unchanged": 0,
                "failed": 1,
                "deleted": 0,
                "offline": False,
            }
    elif not source.root_path:
        source.status = "offline"
        source.error_summary = (
            "Source location is unavailable; reselect the source to relink it."
        )
        return {
            "indexed": 0,
            "unchanged": 0,
            "failed": 0,
            "deleted": 0,
            "offline": True,
        }
    else:
        try:
            source_root = _validated_snapshot_root(source)
        except DocumentParseError as exc:
            if exc.code == "source_offline":
                source.status = "offline"
                source.availability = "offline"
                source.error_summary = (
                    "Source snapshot is unavailable. Indexed documents were preserved."
                )
                return {
                    "indexed": 0,
                    "unchanged": 0,
                    "failed": 0,
                    "deleted": 0,
                    "offline": True,
                }
            source.status = "failed"
            source.availability = "unsafe"
            source.error_summary = (
                "Source snapshot is outside the application-managed storage boundary."
            )
            return {
                "indexed": 0,
                "unchanged": 0,
                "failed": 1,
                "deleted": 0,
                "offline": False,
            }
    source.status = "scanning"
    existing_rows = (
        (
            await db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.source_id == source.id
                )
            )
        )
        .scalars()
        .all()
    )
    known_hashes = {
        item.relative_name: item.hash for item in existing_rows if item.relative_name
    }
    force_parse_names = _embedded_dependency_names(existing_rows)
    try:
        scan = await asyncio.to_thread(
            scan_directory,
            str(source_root),
            known_hashes=known_hashes,
            force_parse_names=force_parse_names,
        )
    except DocumentParseError as exc:
        if str(exc) == "source_offline":
            source.status = "offline"
            source.availability = "offline"
            source.error_summary = (
                "Source location is offline. Indexed documents were preserved."
            )
            return {
                "indexed": 0,
                "unchanged": 0,
                "failed": 0,
                "deleted": 0,
                "offline": True,
            }
        source.status = "failed"
        source.error_summary = "Source could not be scanned safely."
        return {
            "indexed": 0,
            "unchanged": 0,
            "failed": 1,
            "deleted": 0,
            "offline": False,
        }
    selected = source.metadata_json.get("selected_paths")
    if isinstance(selected, list) and not source.local_root_path:
        selected_set = set(str(item) for item in selected)
        files = [item for item in scan.files if item.relative_name in selected_set]
        unchanged_files = [item for item in scan.unchanged if item[0] in selected_set]
        scan = type(scan)(
            files,
            scan.unsupported,
            scan.oversized,
            scan.unsafe_links,
            scan.scanned,
            scan.failed,
            scan.errors,
            unchanged_files,
        )
    scan_files = _expand_markdown_embeds(scan.files)
    source.status = "indexing"
    existing_by_name = {
        item.relative_name: item for item in existing_rows if item.relative_name
    }
    failed_names = {item.get("relative_name") for item in scan.errors}
    failed_prefixes = [
        item.get("relative_name", "")
        for item in scan.errors
        if item.get("code") in {"directory_read_failed", "unsafe_directory_link"}
    ]
    indexed = failed = 0
    unchanged = 0
    for relative_name, size_bytes, modified_ns, file_hash in scan.unchanged:
        existing = existing_by_name.pop(relative_name, None)
        if existing is None or existing.hash != file_hash:
            continue
        known_modified_ns = existing.knowledge_metadata.get("source_modified_ns")
        if known_modified_ns != modified_ns:
            existing.size_bytes = size_bytes
            existing.updated_at = datetime.fromtimestamp(
                modified_ns / 1_000_000_000, UTC
            )
            existing.knowledge_metadata = {
                **existing.knowledge_metadata,
                "source_modified_ns": modified_ns,
            }
        unchanged += 1
    index_errors: list[dict[str, str]] = []
    for parsed_file in scan_files:
        existing = existing_by_name.get(parsed_file.relative_name)
        if existing is None:
            same_content = [
                candidate
                for candidate in existing_by_name.values()
                if candidate.hash == parsed_file.file_hash
            ]
            if len(same_content) == 1:
                existing = same_content[0]
                if existing.relative_name:
                    existing_by_name.pop(existing.relative_name, None)
        if (
            existing
            and existing.hash == parsed_file.file_hash
            and existing.relative_name == parsed_file.relative_name
            and existing.knowledge_metadata.get("embed_hashes", {})
            == parsed_file.embed_hashes
        ):
            existing_by_name.pop(parsed_file.relative_name, None)
            unchanged += 1
            continue
        try:
            async with db.begin_nested():
                await _upsert_document(db, source, parsed_file, existing)
            indexed += 1
        except Exception:
            # One malformed item cannot abort an otherwise useful source sync.
            failed += 1
            safe_error = {
                "relative_name": parsed_file.relative_name,
                "code": "index_failed",
            }
            index_errors.append(safe_error)
            await record_event(
                db,
                action="knowledge.document_failed",
                resource_type="knowledge_source",
                resource_id=source.id,
                metadata=safe_error,
            )
        existing_by_name.pop(parsed_file.relative_name, None)
    deleted = 0
    for stale_name, stale in list(existing_by_name.items()):
        if stale_name in failed_names or any(
            not prefix or stale_name.startswith(f"{prefix}/")
            for prefix in failed_prefixes
        ):
            continue
        await _delete_vectors(stale.id)
        await db.delete(stale)
        deleted += 1
    await db.flush()
    document_rows = (
        (
            await db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.source_id == source.id
                )
            )
        )
        .scalars()
        .all()
    )
    await _reconcile_links(db, document_rows)
    source.last_indexed_at = datetime.now(UTC)
    source.last_seen_at = source.last_indexed_at
    source.content_hash = hashlib.sha256(
        "\n".join(
            f"{item.relative_name}:{item.hash}"
            for item in sorted(
                document_rows, key=lambda value: value.relative_name or ""
            )
        ).encode("utf-8")
    ).hexdigest()
    source.availability = "available"
    source.document_count = len(document_rows)
    source.chunk_count = len(
        (
            await db.execute(
                select(KnowledgeChunk.id)
                .join(KnowledgeDocument)
                .where(KnowledgeDocument.source_id == source.id)
            )
        )
        .scalars()
        .all()
    )
    source.error_summary = (
        "Some documents were skipped or could not be parsed."
        if failed or scan.failed or scan.oversized or scan.unsafe_links
        else None
    )
    source.status = (
        "ready_with_warnings" if source.error_summary or scan.unsupported else "ready"
    )
    source.metadata_json = {
        **source.metadata_json,
        "scan_counts": {
            "scanned": scan.scanned,
            "indexed": indexed,
            "unchanged": unchanged,
            "unsupported": scan.unsupported,
            "oversized": scan.oversized,
            "failed": failed + scan.failed,
            "errors": [*scan.errors, *index_errors][:200],
            "unsafe_links": scan.unsafe_links,
            "deleted": deleted,
        },
    }
    await record_event(
        db,
        action="knowledge.source_synced",
        resource_type="knowledge_source",
        resource_id=source.id,
        metadata={
            "source_type": source.source_type,
            "indexed": indexed,
            "unchanged": unchanged,
            "failed": failed + scan.failed,
            "deleted": deleted,
        },
    )
    return {
        "indexed": indexed,
        "unchanged": unchanged,
        "failed": failed + scan.failed,
        "deleted": deleted,
        "unsupported": scan.unsupported,
        "oversized": scan.oversized,
        "unsafe_links": scan.unsafe_links,
        "offline": False,
    }


async def _upsert_document(
    db: AsyncSession,
    source: KnowledgeSource,
    parsed_file: ParsedFile,
    existing: KnowledgeDocument | None,
) -> None:
    from app.services.knowledge.knowledge_service import (
        _embed_texts,
        get_embedder,
        get_vector_store,
    )

    parsed = parsed_file.parsed_markdown
    if existing is not None:
        await _delete_vectors(existing.id)
        await db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.document_id == existing.id)
        )
    metadata = parsed.metadata if parsed and parsed.metadata else {}
    tags = parsed.tags if parsed else _tags_from_text(parsed_file.content)
    frontmatter_category = metadata.get("category") if metadata else None
    category = (
        _clean(
            str(frontmatter_category) if frontmatter_category else source.category,
            80,
        )
        or "Other"
    )
    title_value = metadata.get("title") if metadata else None
    title = str(title_value) if title_value else Path(parsed_file.relative_name).stem
    if parsed and title == Path(parsed_file.relative_name).stem and parsed.title:
        title = parsed.title
    key = f"{source.id}/{parsed_file.relative_name}"
    document = existing or KnowledgeDocument(
        id=uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"raventech-knowledge:{source.id}:{parsed_file.relative_name}",
        ),
        source_type="osint_notes",
        file_path=key,
        title=title[:500],
        content=parsed_file.content,
        hash=parsed_file.file_hash,
    )
    document.source_type = "osint_notes"
    document.file_path = key
    document.relative_name = parsed_file.relative_name
    document.source_id = source.id
    document.title = title[:500]
    document.content = parsed_file.content
    document.hash = parsed_file.file_hash
    document.tags = tags
    document.created_at = parsed_file.modified_at
    document.updated_at = parsed_file.modified_at
    document.indexed_at = datetime.now(UTC)
    document.content_type = parsed_file.content_type
    document.language = source.language or (
        str(metadata.get("language")) if metadata.get("language") else None
    )
    document.trust_level = source.trust_level
    document.verification_status = source.verification_status
    document.document_status = (
        "sensitive_content_warning"
        if parsed_file.sensitive_content_warning
        else "ready"
    )
    document.size_bytes = parsed_file.size_bytes
    document.knowledge_metadata = {
        "source_name": source.name,
        "frontmatter": metadata,
        "link_aliases": metadata.get("link_aliases", []),
        "aliases": parsed.aliases if parsed else [],
        "wikilinks": parsed.wikilinks if parsed else [],
        "embeds": parsed.embeds if parsed else [],
        "embed_hashes": parsed_file.embed_hashes,
        "sensitive_content_warning": parsed_file.sensitive_content_warning,
        "source_modified_ns": parsed_file.modified_ns,
    }
    if existing is None:
        db.add(document)
    await db.flush()
    duplicate_id = (
        await db.execute(
            select(KnowledgeDocument.id)
            .where(
                KnowledgeDocument.hash == parsed_file.file_hash,
                KnowledgeDocument.id != document.id,
            )
            .order_by(KnowledgeDocument.created_at, KnowledgeDocument.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    duplicate_metadata = (
        {"duplicate_of_document_id": str(duplicate_id)} if duplicate_id else {}
    )
    document.category = category
    document.knowledge_metadata = {
        **document.knowledge_metadata,
        **duplicate_metadata,
    }
    chunks = chunk_document(parsed_file.content)
    vectors: list[list[float]] = []
    vector_available = False
    if chunks:
        try:
            vectors = await _embed_texts(
                get_embedder(), [chunk.content for chunk in chunks]
            )
            vector_available = len(vectors) == len(chunks)
        except Exception:
            vectors = []
    chroma_chunks = []
    for index, chunk in enumerate(chunks):
        chunk_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{source.id}:{parsed_file.relative_name}:{parsed_file.file_hash}:{index}",
        )
        db_chunk = KnowledgeChunk(
            id=chunk_id,
            document_id=document.id,
            content=chunk.content,
            chunk_index=index,
            embedding_metadata={
                "source_id": str(source.id),
                "source_name": source.name,
                "relative_name": parsed_file.relative_name,
                "document_hash": parsed_file.file_hash,
                "heading_path": chunk.heading_path,
                "tags": tags,
                "trust_level": source.trust_level,
                "verification_status": source.verification_status,
                "category": category,
                "language": document.language,
                "indexed_at": document.indexed_at.isoformat()
                if document.indexed_at
                else None,
                "chunk_ordinal": index,
                "page_number": _page_number(chunk.content),
                "content_kind": "code" if _is_code_chunk(chunk.content) else "text",
                "source_type": "osint_notes",
            },
        )
        db.add(db_chunk)
        await db.flush()
        if vector_available:
            from app.services.knowledge.chroma_store import VectorChunk

            chroma_chunks.append(
                VectorChunk(
                    chunk_id=str(db_chunk.id),
                    document_id=document.id,
                    content=chunk.content,
                    metadata={
                        "document_id": str(document.id),
                        "source_id": str(source.id),
                        "source_type": "osint_notes",
                        "file_path": key,
                        "title": document.title,
                        "tags": tags,
                        "trust_level": source.trust_level,
                        "verification_status": source.verification_status,
                        "category": category,
                    },
                    embedding=vectors[index],
                )
            )
    document.knowledge_metadata = {
        **document.knowledge_metadata,
        "vector_indexed": vector_available,
    }
    if chroma_chunks:
        try:
            get_vector_store().upsert_chunks(chroma_chunks)
        except Exception:
            document.knowledge_metadata = {
                **document.knowledge_metadata,
                "vector_indexed": False,
            }


async def _delete_vectors(document_id: uuid.UUID) -> None:
    try:
        from app.services.knowledge.knowledge_service import get_vector_store

        get_vector_store().delete_document(document_id)
    except Exception:
        # PostgreSQL keyword search remains authoritative when vector storage is absent.
        return


def _expand_markdown_embeds(files: list[ParsedFile]) -> list[ParsedFile]:
    """Index one bounded embed level without recursively traversing note graphs."""
    by_path: dict[str, ParsedFile] = {}
    by_stem: dict[str, list[ParsedFile]] = {}
    for item in files:
        by_path[_link_key(item.relative_name)] = item
        by_stem.setdefault(_link_key(Path(item.relative_name).stem), []).append(item)
    expanded: list[ParsedFile] = []
    for item in files:
        markdown = item.parsed_markdown
        if markdown is None or not markdown.embeds:
            expanded.append(item)
            continue
        additions: list[str] = []
        embed_hashes: dict[str, str] = {}
        for target in markdown.embeds[:10]:
            normalized = target.strip().replace("\\", "/")
            if normalized.startswith("/") or ".." in PurePosixPath(normalized).parts:
                continue
            parent = Path(item.relative_name).parent.as_posix()
            relative_target = str(PurePosixPath(parent) / normalized)
            match = by_path.get(_link_key(relative_target))
            if match is None and Path(relative_target).suffix == "":
                match = by_path.get(_link_key(f"{relative_target}.md"))
            if match is None and Path(normalized).suffix == "":
                candidates = by_stem.get(_link_key(Path(normalized).name), [])
                match = candidates[0] if len(candidates) == 1 else None
            if match is None or match.content_type not in {
                "text/markdown",
                "text/plain",
            }:
                continue
            remaining = 200_000 - sum(len(value) for value in additions)
            if remaining <= 0:
                break
            additions.append(
                f"#### Embedded reference: {match.relative_name}\n\n"
                f"{match.content[:remaining]}"
            )
            embed_hashes[match.relative_name] = match.file_hash
        if additions:
            expanded.append(
                replace(
                    item,
                    content=f"{item.content}\n\n---\n\n" + "\n\n".join(additions),
                    embed_hashes=embed_hashes,
                )
            )
        else:
            expanded.append(item)
    return expanded


def _embedded_dependency_names(documents: Sequence[KnowledgeDocument]) -> set[str]:
    """Reparse only notes and note targets needed to reconcile Obsidian embeds."""
    by_path = {
        _link_key(item.relative_name): item.relative_name
        for item in documents
        if item.relative_name
    }
    by_stem: dict[str, list[str]] = {}
    for item in documents:
        if item.relative_name:
            by_stem.setdefault(_link_key(Path(item.relative_name).stem), []).append(
                item.relative_name
            )
    forced: set[str] = set()
    for document in documents:
        if not document.relative_name:
            continue
        embeds = document.knowledge_metadata.get("embeds", [])
        if not isinstance(embeds, list) or not embeds:
            continue
        forced.add(document.relative_name)
        for raw_target in embeds[:10]:
            if not isinstance(raw_target, str) or not raw_target.strip():
                continue
            target = raw_target.strip().replace("\\", "/")
            if target.startswith("/") or ".." in PurePosixPath(target).parts:
                continue
            relative = str(
                PurePosixPath(Path(document.relative_name).parent.as_posix()) / target
            )
            match = by_path.get(_link_key(relative))
            if match is None and Path(relative).suffix == "":
                match = by_path.get(_link_key(f"{relative}.md"))
            if match is None and Path(target).suffix == "":
                candidates = by_stem.get(_link_key(Path(target).name), [])
                match = candidates[0] if len(candidates) == 1 else None
            if match:
                forced.add(match)
    return forced


async def _reconcile_links(
    db: AsyncSession, documents: Sequence[KnowledgeDocument]
) -> None:
    ids = [item.id for item in documents]
    if ids:
        await db.execute(
            delete(KnowledgeLink).where(KnowledgeLink.source_document_id.in_(ids))
        )
    by_path: dict[str, KnowledgeDocument] = {}
    by_stem: dict[str, list[KnowledgeDocument]] = {}
    by_alias: dict[str, list[KnowledgeDocument]] = {}
    for document in documents:
        if not document.relative_name:
            continue
        by_path[_link_key(document.relative_name)] = document
        by_stem.setdefault(_link_key(Path(document.relative_name).stem), []).append(
            document
        )
        for alias in document.knowledge_metadata.get("aliases", []):
            if isinstance(alias, str):
                by_alias.setdefault(_link_key(alias), []).append(document)
    for document in documents:
        wikilinks = document.knowledge_metadata.get("wikilinks", [])
        embeds = set(document.knowledge_metadata.get("embeds", []))
        for target in wikilinks:
            if not isinstance(target, str) or not target.strip():
                continue
            clean_target = target.strip().replace("\\", "/")
            if (
                clean_target.startswith("/")
                or ".." in PurePosixPath(clean_target).parts
            ):
                continue
            resolved = by_path.get(_link_key(clean_target))
            if resolved is None and Path(clean_target).suffix == "":
                resolved = by_path.get(_link_key(f"{clean_target}.md"))
            if resolved is None:
                stems = by_stem.get(_link_key(Path(clean_target).stem), [])
                aliases = by_alias.get(_link_key(clean_target), [])
                candidates = stems if stems else aliases
                resolved = candidates[0] if len(candidates) == 1 else None
            raw_aliases = document.knowledge_metadata.get("link_aliases", [])
            link_aliases = {
                item.split("|", 1)[0]: item.split("|", 1)[1]
                for item in raw_aliases
                if isinstance(item, str) and "|" in item
            }
            db.add(
                KnowledgeLink(
                    source_document_id=document.id,
                    target_document_id=resolved.id if resolved else None,
                    target_name=clean_target[:500],
                    link_alias=link_aliases.get(target),
                    link_kind="embed" if target in embeds else "wikilink",
                    resolved=resolved is not None,
                )
            )


def _link_key(value: str) -> str:
    normalized = str(PurePosixPath(value)).removesuffix(".md")
    return normalized.casefold() if os.name == "nt" else normalized


def _validated_snapshot_root(source: KnowledgeSource) -> Path:
    if not source.root_path:
        raise DocumentParseError("source_offline")
    raw_root = Path(source.root_path).expanduser()
    if raw_root.is_symlink():
        raise DocumentParseError("source_boundary_invalid")
    try:
        root = raw_root.resolve(strict=True)
        expected_parent = import_root().resolve(strict=True)
    except OSError as exc:
        raise DocumentParseError("source_offline") from exc
    if (
        root.parent != expected_parent
        or root.name != str(source.id)
        or not root.is_dir()
    ):
        raise DocumentParseError("source_boundary_invalid")
    try:
        marker = json.loads((root / _SOURCE_MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise DocumentParseError("source_boundary_invalid") from exc
    if marker != {"source_id": str(source.id), "source_type": source.source_type}:
        raise DocumentParseError("source_boundary_invalid")
    return root


def validate_local_vault_root(value: str) -> str:
    """Canonicalize a selected local vault directory without following links."""
    raw = Path(value).expanduser()
    if not raw.is_absolute() or len(str(raw)) > 32767:
        raise ValueError("Selected vault location is invalid.")
    current = Path(raw.anchor)
    for part in raw.parts[1:]:
        current = current / part
        if _is_local_link(current):
            raise ValueError(
                "Selected vault location crosses a symbolic link or reparse point."
            )
    try:
        canonical = raw.resolve(strict=True)
    except OSError:
        raise ValueError("Selected vault location is unavailable.") from None
    if not canonical.is_dir():
        raise ValueError("Selected vault location is not a directory.")
    return str(canonical)


def _resolve_local_vault_root(value: str) -> Path:
    raw = Path(value)
    try:
        return Path(validate_local_vault_root(str(raw)))
    except ValueError as exc:
        if not raw.exists():
            raise DocumentParseError("source_offline") from exc
        raise DocumentParseError("source_boundary_invalid") from exc


def remove_managed_snapshot(source: KnowledgeSource) -> bool:
    """Delete only an app-owned copied snapshot, never the selected original vault."""
    try:
        root = _validated_snapshot_root(source)
    except DocumentParseError:
        return False
    shutil.rmtree(root)
    return True


def _page_number(content: str) -> int | None:
    match = re.search(r"(?m)^\[Page\s+(\d+)\]$", content)
    return int(match.group(1)) if match else None


def _is_local_link(path: Path) -> bool:
    try:
        junction = getattr(path, "is_junction", None)
        return path.is_symlink() or bool(junction and junction())
    except OSError:
        return True


def _clean(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    clean = " ".join(value.strip().split())
    return clean[:limit] or None


def _tags_from_text(content: str) -> list[str]:
    from app.services.knowledge.markdown_parser import parse_markdown

    return parse_markdown(content).tags


def _is_code_chunk(value: str) -> bool:
    return "```" in value or "~~~" in value
