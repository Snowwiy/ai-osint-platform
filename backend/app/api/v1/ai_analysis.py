from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_feature
from app.models.operational_analysis import OperationalAnalysis
from app.models.user import User
from app.schemas.ai_analysis import (
    AnalysisComparisonRequest,
    AnalysisComparisonResponse,
    AnalysisWindow,
    AnalysisWorkflow,
    EvidenceAnalysisListItem,
    EvidenceAnalysisRequest,
    EvidenceAnalysisView,
)
from app.services.ai_analysis.service import (
    AnalysisAccessError,
    AnalysisNotFoundError,
    compare_analysis_rows,
    create_analysis,
    get_analysis,
    list_analyses,
)
from app.services.audit import record_event

router = APIRouter(
    prefix="/ai/analysis",
    tags=["ai-evidence-analysis"],
    dependencies=[Depends(require_feature("enable_ai_analysis"))],
)
_ALLOWED_ROLES = {"admin", "analyst"}


@router.post("/run", response_model=EvidenceAnalysisView)
async def run_evidence_analysis(
    body: EvidenceAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceAnalysisView:
    _require_analyst(current_user)
    try:
        row, deduplicated = await create_analysis(db, current_user, body)
    except AnalysisAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    await record_event(
        db,
        action="ai.evidence_analysis.completed",
        actor_id=current_user.id,
        resource_type="ai_operational_analysis",
        resource_id=row.id,
        metadata={
            "workflow": row.workflow,
            "scope_type": row.scope_type,
            "bundle_sha256": row.bundle_sha256,
            "evidence_count": row.evidence_count,
            "deduplicated": deduplicated,
            "mode": "deterministic",
        },
    )
    await db.commit()
    await db.refresh(row)
    return _view(row, deduplicated=deduplicated)


@router.get("/history", response_model=list[EvidenceAnalysisListItem])
async def analysis_history(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EvidenceAnalysisListItem]:
    _require_analyst(current_user)
    rows = await list_analyses(db, current_user, limit=limit, offset=offset)
    return [_list_item(row) for row in rows]


@router.post("/compare", response_model=AnalysisComparisonResponse)
async def compare_analyses(
    body: AnalysisComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisComparisonResponse:
    _require_analyst(current_user)
    try:
        first = await get_analysis(db, current_user, body.first_analysis_id)
        second = await get_analysis(db, current_user, body.second_analysis_id)
    except AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    if first.workflow != second.workflow or first.scope_id != second.scope_id:
        raise HTTPException(
            status_code=422,
            detail="Only analyses for the same workflow and scope can be compared.",
        )
    return AnalysisComparisonResponse.model_validate(
        compare_analysis_rows(first, second)
    )


@router.post("/{analysis_id}/rerun", response_model=EvidenceAnalysisView)
async def rerun_analysis(
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceAnalysisView:
    _require_analyst(current_user)
    try:
        previous = await get_analysis(db, current_user, analysis_id)
        label = str(previous.window.get("label", "1h"))
        allowed = {"15m", "1h", "6h", "12h", "24h", "7d"}
        request = EvidenceAnalysisRequest(
            workflow=cast(AnalysisWorkflow, previous.workflow),
            window=cast(AnalysisWindow, label if label in allowed else "1h"),
            resource=previous.result.get("resource"),
            scope_id=uuid.UUID(previous.scope_id) if previous.scope_id else None,
        )
        row, _ = await create_analysis(db, current_user, request, force_new=True)
    except AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except AnalysisAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    await record_event(
        db,
        action="ai.evidence_analysis.rerun",
        actor_id=current_user.id,
        resource_type="ai_operational_analysis",
        resource_id=row.id,
        metadata={"workflow": row.workflow, "bundle_sha256": row.bundle_sha256},
    )
    await db.commit()
    await db.refresh(row)
    return _view(row)


@router.get("/{analysis_id}", response_model=EvidenceAnalysisView)
async def analysis_detail(
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceAnalysisView:
    _require_analyst(current_user)
    try:
        row = await get_analysis(db, current_user, analysis_id)
    except AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return _view(row)


def _require_analyst(user: User) -> None:
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(
            status_code=403, detail="Analyst or administrator access is required."
        )


def _view(
    row: OperationalAnalysis, *, deduplicated: bool = False
) -> EvidenceAnalysisView:
    return EvidenceAnalysisView(
        id=row.id,
        workflow=cast(Any, row.workflow),
        scope_type=row.scope_type,
        scope_id=row.scope_id,
        generated_at=row.created_at,
        window=row.window,
        status=cast(Any, row.status),
        summary=row.summary,
        confidence=cast(Any, row.confidence),
        evidence_count=row.evidence_count,
        bundle_sha256=row.bundle_sha256,
        result=row.result,
        model_metadata=row.model_metadata,
        deduplicated=deduplicated,
    )


def _list_item(row: OperationalAnalysis) -> EvidenceAnalysisListItem:
    return EvidenceAnalysisListItem(
        id=row.id,
        workflow=row.workflow,
        scope_type=row.scope_type,
        scope_id=row.scope_id,
        generated_at=row.created_at,
        status=row.status,
        summary=row.summary,
        confidence=cast(Any, row.confidence),
        evidence_count=row.evidence_count,
        bundle_sha256=row.bundle_sha256,
    )
