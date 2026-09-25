from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.background_job import BackgroundJob
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.models.knowledge_link import KnowledgeLink
from app.models.knowledge_source import KnowledgeSource
from app.models.user import User
from app.schemas.defensive_intelligence import (
    DetectionKnowledgeResponse,
    FrameworkKnowledgeResponse,
)
from app.schemas.ioc import IOCGuidanceResponse
from app.schemas.knowledge import (
    KnowledgeDocumentListResponse,
    KnowledgeSearchMode,
    KnowledgeSearchResponse,
    KnowledgeSourceListResponse,
    KnowledgeSourcePatch,
    KnowledgeSourceResponse,
    KnowledgeSourceType,
    KnowledgeStatsResponse,
)
from app.services.audit import record_event
from app.services.background_jobs import PRIORITIES, enqueue_job
from app.services.defensive_intelligence import (
    list_detection_knowledge,
    list_framework_knowledge,
)
from app.services.ioc_intelligence import list_ioc_guidance
from app.services.knowledge.knowledge_service import (
    KnowledgeSearchFilters,
    list_knowledge_documents,
    search_knowledge,
)
from app.services.knowledge.source_service import (
    create_uploaded_source,
    remove_managed_snapshot,
    update_uploaded_source_files,
    validate_source_metadata,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/index", status_code=410)
async def legacy_path_indexing_disabled(
    _body: dict[str, Any],
    _admin: User = Depends(require_role("admin")),
) -> dict[str, str]:
    raise HTTPException(
        status_code=410,
        detail=(
            "Direct filesystem path indexing is disabled. Select files or a vault "
            "in the desktop Knowledge view."
        ),
    )


@router.get("/sources", response_model=KnowledgeSourceListResponse)
async def list_knowledge_sources_endpoint(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSourceListResponse:
    sources = (
        (
            await db.execute(
                select(KnowledgeSource).order_by(KnowledgeSource.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return KnowledgeSourceListResponse(
        total=len(sources), items=[_source_response(item) for item in sources]
    )


@router.get("/sources/{source_id}", response_model=KnowledgeSourceResponse)
async def get_knowledge_source_endpoint(
    source_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSourceResponse:
    source = await db.get(KnowledgeSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found.")
    return _source_response(source)


@router.get("/documents/{document_id}")
async def get_knowledge_document_endpoint(
    document_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    document = await db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    links = (
        (
            await db.execute(
                select(KnowledgeLink).where(
                    KnowledgeLink.source_document_id == document.id
                )
            )
        )
        .scalars()
        .all()
    )
    source = (
        await db.get(KnowledgeSource, document.source_id)
        if document.source_id
        else None
    )
    return {
        "id": str(document.id),
        "title": document.title,
        "source_id": str(document.source_id) if document.source_id else None,
        "source_name": source.name if source else None,
        "relative_name": document.relative_name,
        "category": document.category,
        "content_type": document.content_type,
        "language": document.language,
        "hash": document.hash,
        "modified_at": document.updated_at,
        "indexed_at": document.indexed_at,
        "tags": document.tags,
        "trust_level": document.trust_level,
        "verification_status": document.verification_status,
        "status": document.document_status,
        "content": document.content,
        "metadata": document.knowledge_metadata,
        "references": [
            {
                "target": link.target_name,
                "alias": link.link_alias,
                "resolved": link.resolved,
                "kind": link.link_kind,
                "target_document_id": str(link.target_document_id)
                if link.target_document_id
                else None,
            }
            for link in links
        ],
    }


@router.post(
    "/sources/obsidian-vault", response_model=KnowledgeSourceResponse, status_code=202
)
async def add_obsidian_vault_endpoint(
    request: Request,
    name: str = Form(min_length=1, max_length=200),
    trust_level: str = Form(default="unknown"),
    verification_status: str = Form(default="unverified"),
    category: str = Form(default="Other", max_length=80),
    language: str | None = Form(default=None, max_length=16),
    publisher: str | None = Form(default=None, max_length=200),
    canonical_url: str | None = Form(default=None, max_length=1000),
    publication_date: str | None = Form(default=None, max_length=40),
    version_label: str | None = Form(default=None, max_length=120),
    notes: str | None = Form(default=None, max_length=2000),
    source_root_path: str | None = Form(default=None, max_length=32767),
    file_mtimes_ms: list[str] | None = Form(default=None),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSourceResponse:
    _require_native_picker(request)
    if settings_native_jobs_unavailable():
        raise HTTPException(
            status_code=409,
            detail="Knowledge ingestion requires the native PostgreSQL worker.",
        )
    uploaded = await _read_selected_files(files, file_mtimes_ms)
    try:
        source = await create_uploaded_source(
            db,
            name=name,
            source_type="obsidian_vault",
            files=uploaded,
            trust_level=trust_level,
            verification_status=verification_status,
            category=category,
            language=language,
            publisher=publisher,
            canonical_url=canonical_url,
            publication_date=publication_date,
            version_label=version_label,
            notes=notes,
            local_root_path=source_root_path,
        )
        await _queue_source_sync(db, source, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    await record_event(
        db,
        action="knowledge.source_added",
        actor_id=current_user.id,
        resource_type="knowledge_source",
        resource_id=source.id,
        metadata={"source_type": source.source_type, "name": source.name},
    )
    # Audit/job dispatch may flush or commit through the same session. Refresh
    # server-managed timestamps before building the response so AsyncSession
    # never tries to lazy-load an expired attribute during serialization.
    await db.flush()
    await db.refresh(source)
    return _source_response(source)


@router.post("/sources/upload", response_model=KnowledgeSourceResponse, status_code=202)
async def add_document_source_endpoint(
    request: Request,
    name: str = Form(min_length=1, max_length=200),
    trust_level: str = Form(default="unknown"),
    verification_status: str = Form(default="unverified"),
    category: str = Form(default="Other", max_length=80),
    publisher: str | None = Form(default=None, max_length=200),
    canonical_url: str | None = Form(default=None, max_length=1000),
    publication_date: str | None = Form(default=None, max_length=40),
    version_label: str | None = Form(default=None, max_length=120),
    notes: str | None = Form(default=None, max_length=2000),
    language: str | None = Form(default=None, max_length=16),
    file_mtimes_ms: list[str] | None = Form(default=None),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSourceResponse:
    _require_native_picker(request)
    if settings_native_jobs_unavailable():
        raise HTTPException(
            status_code=409,
            detail="Knowledge ingestion requires the native PostgreSQL worker.",
        )
    uploaded = await _read_selected_files(files, file_mtimes_ms)
    try:
        source = await create_uploaded_source(
            db,
            name=name,
            source_type="document_upload",
            files=uploaded,
            trust_level=trust_level,
            verification_status=verification_status,
            category=category,
            publisher=publisher,
            canonical_url=canonical_url,
            publication_date=publication_date,
            version_label=version_label,
            notes=notes,
            language=language,
        )
        await _queue_source_sync(db, source, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    await record_event(
        db,
        action="knowledge.source_added",
        actor_id=current_user.id,
        resource_type="knowledge_source",
        resource_id=source.id,
        metadata={"source_type": source.source_type, "name": source.name},
    )
    await db.flush()
    await db.refresh(source)
    return _source_response(source)


@router.post(
    "/sources/{source_id}/upload",
    response_model=KnowledgeSourceResponse,
    status_code=202,
)
async def update_knowledge_source_upload_endpoint(
    source_id: uuid.UUID,
    request: Request,
    files: list[UploadFile] = File(...),
    source_root_path: str | None = Form(default=None, max_length=32767),
    file_mtimes_ms: list[str] | None = Form(default=None),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSourceResponse:
    _require_native_picker(request)
    if settings_native_jobs_unavailable():
        raise HTTPException(
            status_code=409,
            detail="Knowledge ingestion requires the native PostgreSQL worker.",
        )
    source = await db.get(KnowledgeSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found.")
    if source.status == "disabled":
        raise HTTPException(
            status_code=409, detail="Disabled Knowledge sources cannot be refreshed."
        )
    uploaded = await _read_selected_files(files, file_mtimes_ms)
    try:
        selected = await update_uploaded_source_files(source, uploaded)
        if source_root_path:
            if source.source_type != "obsidian_vault":
                raise ValueError(
                    "Only an Obsidian vault can retain a local source location."
                )
            from app.services.knowledge.source_service import validate_local_vault_root

            source.local_root_path = validate_local_vault_root(source_root_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    source.metadata_json = {**source.metadata_json, "selected_paths": selected}
    source.status = "pending"
    await _queue_source_sync(db, source, current_user)
    await db.flush()
    await db.refresh(source)
    return _source_response(source)


@router.post(
    "/sources/{source_id}/sync", response_model=KnowledgeSourceResponse, status_code=202
)
async def sync_knowledge_source_endpoint(
    source_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSourceResponse:
    _require_native_picker(request)
    source = await db.get(KnowledgeSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found.")
    if source.status == "disabled":
        raise HTTPException(
            status_code=409, detail="Disabled Knowledge sources cannot be synchronized."
        )
    if settings_native_jobs_unavailable():
        raise HTTPException(
            status_code=409,
            detail="Knowledge ingestion requires the native PostgreSQL worker.",
        )
    source.status = "pending"
    await _queue_source_sync(db, source, current_user)
    await db.flush()
    await db.refresh(source)
    return _source_response(source)


@router.patch("/sources/{source_id}", response_model=KnowledgeSourceResponse)
async def update_knowledge_source_endpoint(
    source_id: uuid.UUID,
    body: KnowledgeSourcePatch,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSourceResponse:
    source = await db.get(KnowledgeSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found.")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("canonical_url"):
        try:
            validate_source_metadata(
                source_type=source.source_type,
                trust_level=source.trust_level,
                verification_status=source.verification_status,
                canonical_url=changes["canonical_url"],
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
    old_trust = source.trust_level
    old_verification = source.verification_status
    disabled = (
        changes.pop("status", None) == "disabled" if "status" in changes else None
    )
    for key, value in changes.items():
        if isinstance(value, str):
            clean_value = value.strip()
            if key in {
                "publisher",
                "canonical_url",
                "publication_date",
                "version_label",
                "language",
                "notes",
            }:
                value = clean_value or None
            else:
                value = clean_value
        setattr(source, key, value)
    if disabled is not None:
        source.status = (
            "disabled"
            if disabled
            else ("ready" if source.document_count else "pending")
        )
    if source.trust_level != old_trust:
        await _propagate_document_source_state(db, source)
        await record_event(
            db,
            action="knowledge.trust_changed",
            actor_id=current_user.id,
            resource_type="knowledge_source",
            resource_id=source.id,
            metadata={"trust_level": source.trust_level},
        )
    if source.verification_status != old_verification:
        await _propagate_document_source_state(db, source)
        await record_event(
            db,
            action="knowledge.verification_changed",
            actor_id=current_user.id,
            resource_type="knowledge_source",
            resource_id=source.id,
            metadata={"verification_status": source.verification_status},
        )
    if "category" in changes:
        await _propagate_document_source_state(db, source)
        await record_event(
            db,
            action="knowledge.category_changed",
            actor_id=current_user.id,
            resource_type="knowledge_source",
            resource_id=source.id,
            metadata={"category": source.category},
        )
    metadata_keys = sorted(
        set(changes)
        & {
            "publisher",
            "canonical_url",
            "publication_date",
            "version_label",
            "language",
            "notes",
        }
    )
    if metadata_keys:
        await record_event(
            db,
            action="knowledge.source_metadata_changed",
            actor_id=current_user.id,
            resource_type="knowledge_source",
            resource_id=source.id,
            metadata={"fields": metadata_keys},
        )
    if disabled is not None:
        await record_event(
            db,
            action="knowledge.source_disabled"
            if disabled
            else "knowledge.source_enabled",
            actor_id=current_user.id,
            resource_type="knowledge_source",
            resource_id=source.id,
            metadata={"source_type": source.source_type},
        )
    await db.flush()
    await db.refresh(source)
    return _source_response(source)


@router.delete("/sources/{source_id}", status_code=204)
async def remove_knowledge_source_endpoint(
    source_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    source = await db.get(KnowledgeSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found.")
    documents = (
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
    from app.services.knowledge.knowledge_service import get_vector_store

    snapshot = source

    for document in documents:
        try:
            get_vector_store().delete_document(document.id)
        except Exception:
            pass
        await db.delete(document)
    await db.flush()
    await db.delete(source)
    await record_event(
        db,
        action="knowledge.source_removed",
        actor_id=current_user.id,
        resource_type="knowledge_source",
        resource_id=source_id,
        metadata={
            "document_count": len(documents),
            "original_files_deleted": False,
            "managed_snapshot_cleanup_attempted": True,
        },
    )
    await db.commit()
    try:
        await asyncio.to_thread(remove_managed_snapshot, snapshot)
    except OSError:
        # The index is already removed; an unexpected local cleanup error leaves
        # only the app-managed copy and never targets the selected original.
        pass


@router.get("/stats", response_model=KnowledgeStatsResponse)
async def knowledge_stats_endpoint(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeStatsResponse:
    sources = (await db.execute(select(KnowledgeSource))).scalars().all()
    documents = (await db.execute(select(KnowledgeDocument))).scalars().all()
    chunks = (await db.execute(select(KnowledgeChunk.id))).scalars().all()
    jobs = (
        (
            await db.execute(
                select(BackgroundJob).where(
                    BackgroundJob.job_type == "knowledge.source.sync",
                    BackgroundJob.status.in_(
                        ("queued", "scheduled", "running", "retry_wait")
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    return KnowledgeStatsResponse(
        sources=len(sources),
        documents=len(documents),
        chunks=len(chunks),
        verified_sources=sum(
            item.verification_status == "verified" for item in sources
        ),
        unverified_sources=sum(
            item.verification_status == "unverified" for item in sources
        ),
        failed_documents=sum(item.document_status == "failed" for item in documents)
        + sum(
            int(item.metadata_json.get("scan_counts", {}).get("failed", 0))
            for item in sources
        ),
        offline_sources=sum(item.status == "offline" for item in sources),
        active_jobs=len(jobs),
        last_sync_at=max(
            (item.last_indexed_at for item in sources if item.last_indexed_at),
            default=None,
        ),
    )


@router.get("/documents", response_model=KnowledgeDocumentListResponse)
async def list_knowledge_documents_endpoint(
    source_type: KnowledgeSourceType | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    source_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentListResponse:
    return await list_knowledge_documents(
        db,
        source_type=source_type,
        tags=tags,
        source_id=source_id,
        skip=skip,
        limit=limit,
    )


@router.get("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge_endpoint(
    q: str = Query(min_length=1, max_length=500),
    mode: KnowledgeSearchMode = Query(default="hybrid"),
    source_type: KnowledgeSourceType | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    source_id: uuid.UUID | None = Query(default=None),
    trust_level: str | None = Query(
        default=None, pattern="^(authoritative|trusted|internal|community|unknown)$"
    ),
    verified_only: bool = Query(default=False),
    language: str | None = Query(default=None, max_length=16),
    category: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=10, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSearchResponse:
    return await search_knowledge(
        db,
        query=q,
        mode=mode,
        filters=KnowledgeSearchFilters(
            source_type=source_type,
            tags=tags,
            source_id=source_id,
            trust_level=trust_level,
            verified_only=verified_only,
            language=language,
            category=category,
        ),
        limit=limit,
    )


@router.get("/detections", response_model=DetectionKnowledgeResponse)
async def list_detection_knowledge_endpoint(
    kind: str | None = Query(default=None, pattern="^(sigma|yara)$"),
    q: str | None = Query(default=None, min_length=1, max_length=200),
    _user: User = Depends(get_current_user),
) -> DetectionKnowledgeResponse:
    return list_detection_knowledge(kind=kind, query=q)


@router.get("/frameworks", response_model=FrameworkKnowledgeResponse)
async def list_framework_knowledge_endpoint(
    framework: str | None = Query(default=None, min_length=1, max_length=100),
    _user: User = Depends(get_current_user),
) -> FrameworkKnowledgeResponse:
    return list_framework_knowledge(framework)


@router.get("/ioc-guidance", response_model=IOCGuidanceResponse)
async def list_ioc_guidance_endpoint(
    q: str | None = Query(default=None, min_length=1, max_length=200),
    _user: User = Depends(get_current_user),
) -> IOCGuidanceResponse:
    return list_ioc_guidance(q)


def settings_native_jobs_unavailable() -> bool:
    from app.core.config import settings

    return settings.background_engine != "native"


def _require_native_picker(request: Request) -> None:
    from app.core.config import settings

    allowed_origins = {"tauri://localhost", "http://tauri.localhost"}
    if (
        settings.RUNTIME_PROFILE != "desktop"
        or request.headers.get("origin", "").rstrip("/") not in allowed_origins
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Knowledge source file selection is available only in the native "
                "desktop application."
            ),
        )


async def _read_selected_files(
    files: list[UploadFile], file_mtimes_ms: list[str] | None = None
) -> list[tuple[str, bytes, int]]:
    from app.core.config import settings

    result: list[tuple[str, bytes, int]] = []
    total = 0
    timestamps = file_mtimes_ms or []
    now_ns = int(datetime.now(UTC).timestamp() * 1_000_000_000)
    try:
        if not files or len(files) > settings.KNOWLEDGE_MAX_UPLOAD_FILES:
            raise HTTPException(
                status_code=413,
                detail="Selected file count exceeds the configured limit.",
            )
        if timestamps and len(timestamps) != len(files):
            raise HTTPException(
                status_code=422,
                detail="Selected file metadata does not match the upload.",
            )
        for index, upload in enumerate(files):
            name = upload.filename or ""
            remaining = max(0, settings.KNOWLEDGE_MAX_UPLOAD_BYTES - total)
            body = await upload.read(remaining + 1)
            total += len(body)
            if total > settings.KNOWLEDGE_MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="Selected files exceed the configured upload limit.",
                )
            modified_ns = now_ns
            if timestamps:
                try:
                    modified_ms = int(timestamps[index])
                except ValueError:
                    raise HTTPException(
                        status_code=422, detail="Selected file metadata is invalid."
                    ) from None
                if modified_ms < 0 or modified_ms > (now_ns // 1_000_000) + 86_400_000:
                    raise HTTPException(
                        status_code=422, detail="Selected file metadata is invalid."
                    )
                modified_ns = modified_ms * 1_000_000
            result.append((name, body, modified_ns))
    finally:
        await asyncio.gather(*(upload.close() for upload in files))
    return result


async def _queue_source_sync(
    db: AsyncSession, source: KnowledgeSource, current_user: User
) -> BackgroundJob:
    return await enqueue_job(
        db,
        "knowledge.source.sync",
        {"source_id": str(source.id)},
        priority=PRIORITIES["high"],
        dedupe_key=f"knowledge-source:{source.id}",
        requested_by_user_id=current_user.id,
        cooldown_seconds=15,
    )


async def _propagate_document_source_state(
    db: AsyncSession, source: KnowledgeSource
) -> None:
    documents = (
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
    for document in documents:
        document.trust_level = source.trust_level
        document.verification_status = source.verification_status
        document.category = source.category
        chunks = (
            (
                await db.execute(
                    select(KnowledgeChunk).where(
                        KnowledgeChunk.document_id == document.id
                    )
                )
            )
            .scalars()
            .all()
        )
        for chunk in chunks:
            chunk.embedding_metadata = {
                **chunk.embedding_metadata,
                "trust_level": source.trust_level,
                "verification_status": source.verification_status,
                "category": source.category,
            }


def _source_response(source: KnowledgeSource) -> KnowledgeSourceResponse:
    counts = source.metadata_json.get("scan_counts", {})
    safe_counts = (
        {
            str(key): int(value)
            for key, value in counts.items()
            if isinstance(value, int)
        }
        if isinstance(counts, dict)
        else {}
    )
    return KnowledgeSourceResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        display_location=source.display_location,
        category=source.category,
        platform=source.platform,
        availability=source.availability,
        status=source.status,
        trust_level=source.trust_level,
        verification_status=source.verification_status,
        language=source.language,
        publisher=source.publisher,
        canonical_url=source.canonical_url,
        publication_date=source.publication_date,
        version_label=source.version_label,
        notes=source.notes,
        last_indexed_at=source.last_indexed_at,
        last_seen_at=source.last_seen_at,
        document_count=source.document_count,
        chunk_count=source.chunk_count,
        error_summary=source.error_summary,
        scan_counts=safe_counts,
        content_hash=source.content_hash,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )
