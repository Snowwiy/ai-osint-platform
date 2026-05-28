from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.analysis import (
    AnalysisResponse,
    InvestigationAnalysisRequest,
    IocAnalysisRequest,
    ThreatContextAnalysisRequest,
)
from app.schemas.knowledge import (
    KnowledgeChunk,
    KnowledgeCitation,
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResponse,
)
from app.services.ai.analyst_service import (
    analyze_investigation,
    analyze_ioc,
    analyze_threat_context,
)
from app.services.investigation import InvestigationNotFoundError
from app.services.knowledge.retriever import retrieve_context

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/investigation", response_model=AnalysisResponse)
async def analyze_investigation_endpoint(
    body: InvestigationAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    try:
        return await analyze_investigation(db, current_user, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post("/ioc", response_model=AnalysisResponse)
async def analyze_ioc_endpoint(
    body: IocAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    try:
        return await analyze_ioc(db, current_user, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post("/threat-context", response_model=AnalysisResponse)
async def analyze_threat_context_endpoint(
    body: ThreatContextAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    try:
        return await analyze_threat_context(db, current_user, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post("/knowledge/search", response_model=KnowledgeRetrievalResponse)
async def search_analysis_knowledge_endpoint(
    body: KnowledgeRetrievalRequest,
    _current_user: User = Depends(get_current_user),
) -> KnowledgeRetrievalResponse:
    result = retrieve_context(
        body.query,
        frameworks=body.frameworks,
        top_k=body.top_k,
    )
    return KnowledgeRetrievalResponse(
        query=result.query,
        matched_chunks=[
            KnowledgeChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                title=chunk.title,
                source=chunk.source,
                framework=chunk.framework,
                category=chunk.category,
                content=chunk.content,
                tags=chunk.tags,
                confidence=chunk.confidence,
                created_at=chunk.created_at,
            )
            for chunk in result.matched_chunks
        ],
        citation_ids=result.citation_ids,
        citations=[
            KnowledgeCitation(
                id=citation.id,
                document_id=citation.document_id,
                chunk_id=citation.chunk_id,
                title=citation.title,
                source=citation.source,
                framework=citation.framework,
                category=citation.category,
                confidence=citation.confidence,
            )
            for citation in result.citations
        ],
        frameworks=result.frameworks,
        confidence=result.confidence,
    )
