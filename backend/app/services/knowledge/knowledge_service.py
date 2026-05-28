from __future__ import annotations

import inspect
import uuid
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.schemas.knowledge import (
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    KnowledgeIndexResponse,
    KnowledgeSearchMode,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
    KnowledgeSourceType,
)
from app.services.knowledge.chroma_store import (
    ChromaKnowledgeStore,
    VectorChunk,
    VectorFilters,
)
from app.services.knowledge.document_chunker import chunk_document
from app.services.knowledge.document_loader import (
    load_documents_from_paths,
)
from app.services.knowledge.embeddings import LocalSentenceTransformerEmbedder
from app.services.knowledge.markdown_parser import parse_markdown


@dataclass(frozen=True)
class KnowledgeSearchFilters:
    source_type: KnowledgeSourceType | None = None
    tags: list[str] | None = None


def get_embedder() -> LocalSentenceTransformerEmbedder:
    return LocalSentenceTransformerEmbedder()


def get_vector_store() -> ChromaKnowledgeStore:
    return ChromaKnowledgeStore(settings.CHROMA_DATA_PATH)


async def index_knowledge_sources(
    db: AsyncSession,
    *,
    source_type: KnowledgeSourceType,
    paths: list[str],
) -> KnowledgeIndexResponse:
    resolved_paths = paths or _configured_paths()
    loaded_documents = load_documents_from_paths(
        resolved_paths, source_type=source_type
    )
    embedder = get_embedder()
    vector_store = get_vector_store()
    indexed = 0
    skipped = 0
    chunks_indexed = 0
    for loaded in loaded_documents:
        if await _document_with_hash_exists(db, loaded.file_hash):
            skipped += 1
            continue
        existing = await _document_by_path(db, str(loaded.path))
        if existing is not None:
            vector_store.delete_document(existing.id)
            await db.delete(existing)
            await db.flush()

        parsed = parse_markdown(loaded.content)
        document = KnowledgeDocument(
            source_type=source_type,
            file_path=str(loaded.path),
            title=parsed.title,
            content=loaded.content,
            hash=loaded.file_hash,
            tags=parsed.tags,
            created_at=loaded.created_at,
            updated_at=loaded.updated_at,
        )
        db.add(document)
        await db.flush()

        chunks = chunk_document(loaded.content)
        vectors = await _embed_texts(embedder, [chunk.content for chunk in chunks])
        vector_chunks: list[VectorChunk] = []
        for chunk, vector in zip(chunks, vectors, strict=False):
            db_chunk = KnowledgeChunk(
                document_id=document.id,
                content=chunk.content,
                chunk_index=chunk.chunk_index,
                embedding_metadata={
                    "source_type": source_type,
                    "file_hash": loaded.file_hash,
                    "heading_path": chunk.heading_path,
                    "tags": parsed.tags,
                    "wikilinks": parsed.wikilinks,
                    "title": parsed.title,
                },
            )
            db.add(db_chunk)
            await db.flush()
            vector_chunks.append(
                VectorChunk(
                    chunk_id=str(db_chunk.id),
                    document_id=document.id,
                    content=chunk.content,
                    metadata={
                        "document_id": str(document.id),
                        "source_type": source_type,
                        "file_path": str(loaded.path),
                        "title": parsed.title,
                        "tags": parsed.tags,
                        "file_hash": loaded.file_hash,
                    },
                    embedding=vector,
                )
            )
        vector_store.upsert_chunks(vector_chunks)
        indexed += 1
        chunks_indexed += len(vector_chunks)

    return KnowledgeIndexResponse(
        documents_seen=len(loaded_documents),
        documents_indexed=indexed,
        documents_skipped=skipped,
        chunks_indexed=chunks_indexed,
    )


async def list_knowledge_documents(
    db: AsyncSession,
    *,
    source_type: KnowledgeSourceType | None = None,
    tags: list[str] | None = None,
    skip: int = 0,
    limit: int = 50,
) -> KnowledgeDocumentListResponse:
    filters = []
    if source_type is not None:
        filters.append(KnowledgeDocument.source_type == source_type)
    if tags:
        filters.append(KnowledgeDocument.tags.contains(tags))
    base = select(KnowledgeDocument).where(*filters)
    total = len((await db.execute(base)).scalars().all())
    result = await db.execute(
        base.order_by(KnowledgeDocument.updated_at.desc()).offset(skip).limit(limit)
    )
    return KnowledgeDocumentListResponse(
        total=total,
        items=[
            KnowledgeDocumentResponse.model_validate(document)
            for document in result.scalars().all()
        ],
    )


async def search_knowledge(
    db: AsyncSession,
    *,
    query: str,
    mode: KnowledgeSearchMode,
    filters: KnowledgeSearchFilters,
    limit: int = 10,
) -> KnowledgeSearchResponse:
    if mode == "keyword":
        results = await _keyword_search(db, query, filters, limit)
    elif mode == "semantic":
        results = await _semantic_search(db, query, filters, limit)
    else:
        keyword = await _keyword_search(db, query, filters, limit)
        semantic = await _semantic_search(db, query, filters, limit)
        results = _merge_results(keyword, semantic, limit)
    return KnowledgeSearchResponse(
        query=query,
        mode=mode,
        total=len(results),
        items=results,
    )


async def _keyword_search(
    db: AsyncSession,
    query: str,
    filters: KnowledgeSearchFilters,
    limit: int,
) -> list[KnowledgeSearchResult]:
    stmt = (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(
            or_(
                KnowledgeChunk.content.ilike(f"%{query}%"),
                KnowledgeDocument.title.ilike(f"%{query}%"),
                KnowledgeDocument.content.ilike(f"%{query}%"),
            )
        )
    )
    stmt = _apply_document_filters(stmt, filters)
    rows = (await db.execute(stmt.limit(limit))).all()
    return [
        _search_result(document, chunk.content, score=1.0) for chunk, document in rows
    ]


async def _semantic_search(
    db: AsyncSession,
    query: str,
    filters: KnowledgeSearchFilters,
    limit: int,
) -> list[KnowledgeSearchResult]:
    embedder = get_embedder()
    vector_store = get_vector_store()
    query_embedding = await _embed_query(embedder, query)
    matches = vector_store.search(
        query_embedding,
        query=query,
        limit=limit,
        filters=VectorFilters(source_type=filters.source_type, tags=filters.tags),
    )
    results: list[KnowledgeSearchResult] = []
    for match in matches:
        document_id = _uuid_or_none(match.get("document_id"))
        if document_id is None:
            continue
        document = await db.get(KnowledgeDocument, document_id)
        if document is None or not _document_matches_filters(document, filters):
            continue
        results.append(
            _search_result(
                document,
                str(match.get("content", "")),
                score=float(match.get("score", 0.0)),
            )
        )
    return results


def _merge_results(
    keyword: list[KnowledgeSearchResult],
    semantic: list[KnowledgeSearchResult],
    limit: int,
) -> list[KnowledgeSearchResult]:
    merged: dict[tuple[uuid.UUID, str], KnowledgeSearchResult] = {}
    for item in [*keyword, *semantic]:
        key = (item.document_id, item.chunk)
        if key not in merged or item.score > merged[key].score:
            merged[key] = item
    return sorted(merged.values(), key=lambda item: item.score, reverse=True)[:limit]


def _search_result(
    document: KnowledgeDocument,
    chunk: str,
    *,
    score: float,
) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        document_id=document.id,
        title=document.title,
        source_type=document.source_type,  # type: ignore[arg-type]
        file_path=document.file_path,
        chunk=chunk,
        score=score,
        tags=document.tags,
    )


def _apply_document_filters(stmt: Any, filters: KnowledgeSearchFilters) -> Any:
    if filters.source_type is not None:
        stmt = stmt.where(KnowledgeDocument.source_type == filters.source_type)
    if filters.tags:
        stmt = stmt.where(KnowledgeDocument.tags.contains(filters.tags))
    return stmt


def _document_matches_filters(
    document: KnowledgeDocument,
    filters: KnowledgeSearchFilters,
) -> bool:
    if filters.source_type is not None and document.source_type != filters.source_type:
        return False
    if filters.tags and not set(filters.tags).issubset(set(document.tags)):
        return False
    return True


async def _document_with_hash_exists(db: AsyncSession, file_hash: str) -> bool:
    result = await db.execute(
        select(KnowledgeDocument.id).where(KnowledgeDocument.hash == file_hash)
    )
    return result.scalar_one_or_none() is not None


async def _document_by_path(
    db: AsyncSession,
    file_path: str,
) -> KnowledgeDocument | None:
    result = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.file_path == file_path)
    )
    return result.scalar_one_or_none()


async def _embed_texts(embedder: object, texts: list[str]) -> list[list[float]]:
    provider = cast(Any, embedder)
    if hasattr(provider, "embed_texts_async"):
        result = await provider.embed_texts_async(texts)
        return cast(list[list[float]], result)
    result = provider.embed_texts(texts)
    if inspect.isawaitable(result):
        awaited = await result
        return cast(list[list[float]], awaited)
    return cast(list[list[float]], result)


async def _embed_query(embedder: object, text: str) -> list[float]:
    provider = cast(Any, embedder)
    if hasattr(provider, "embed_query_async"):
        result = await provider.embed_query_async(text)
        return cast(list[float], result)
    result = provider.embed_query(text)
    if inspect.isawaitable(result):
        awaited = await result
        return cast(list[float], awaited)
    return cast(list[float], result)


def _configured_paths() -> list[str]:
    return [settings.OBSIDIAN_WIKI_PATH] if settings.OBSIDIAN_WIKI_PATH else []


def _uuid_or_none(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None
