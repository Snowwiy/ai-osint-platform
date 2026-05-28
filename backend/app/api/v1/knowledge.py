from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeDocumentListResponse,
    KnowledgeIndexRequest,
    KnowledgeIndexResponse,
    KnowledgeSearchMode,
    KnowledgeSearchResponse,
    KnowledgeSourceType,
)
from app.services.knowledge.knowledge_service import (
    KnowledgeSearchFilters,
    index_knowledge_sources,
    list_knowledge_documents,
    search_knowledge,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/index", response_model=KnowledgeIndexResponse)
async def index_knowledge_endpoint(
    body: KnowledgeIndexRequest,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeIndexResponse:
    return await index_knowledge_sources(
        db,
        source_type=body.source_type,
        paths=body.paths,
    )


@router.get("/documents", response_model=KnowledgeDocumentListResponse)
async def list_knowledge_documents_endpoint(
    source_type: KnowledgeSourceType | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentListResponse:
    return await list_knowledge_documents(
        db,
        source_type=source_type,
        tags=tags,
        skip=skip,
        limit=limit,
    )


@router.get("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge_endpoint(
    q: str = Query(min_length=1, max_length=500),
    mode: KnowledgeSearchMode = Query(default="hybrid"),
    source_type: KnowledgeSourceType | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSearchResponse:
    return await search_knowledge(
        db,
        query=q,
        mode=mode,
        filters=KnowledgeSearchFilters(source_type=source_type, tags=tags),
        limit=limit,
    )
