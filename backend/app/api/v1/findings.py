from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.finding import (
    FindingAssignRequest,
    FindingResponse,
    FindingSeverity,
    FindingStatus,
    FindingStatusUpdate,
    FindingSummaryResponse,
)
from app.services.audit import record_event
from app.services.intelligence.findings_service import (
    FindingNotFoundError,
    assign_finding,
    generate_findings_response_for_investigation,
    list_findings_for_investigation,
    summarize_findings_for_investigation,
    update_finding_status,
)
from app.services.investigation import (
    ForbiddenError,
    InvestigationNotFoundError,
    MemberValidationError,
)

router = APIRouter(tags=["findings"])


@router.get(
    "/investigations/{investigation_id}/findings",
    response_model=list[FindingResponse],
)
async def list_findings_endpoint(
    investigation_id: uuid.UUID,
    severity: FindingSeverity | None = Query(default=None),
    status: FindingStatus | None = Query(default=None),
    source: str | None = Query(default=None, min_length=1, max_length=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FindingResponse]:
    try:
        return await list_findings_for_investigation(
            db,
            current_user,
            investigation_id,
            severity=severity,
            status=status,
            source=source,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post(
    "/investigations/{investigation_id}/findings/generate",
    response_model=list[FindingResponse],
)
async def generate_findings_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FindingResponse]:
    try:
        findings = await generate_findings_response_for_investigation(
            db,
            current_user,
            investigation_id,
        )
        await record_event(
            db,
            action="findings.generated",
            actor_id=current_user.id,
            resource_type="investigation",
            resource_id=investigation_id,
            investigation_id=investigation_id,
            metadata={"finding_count": len(findings)},
        )
        return findings
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/investigations/{investigation_id}/findings/summary",
    response_model=FindingSummaryResponse,
)
async def findings_summary_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FindingSummaryResponse:
    try:
        return await summarize_findings_for_investigation(
            db,
            current_user,
            investigation_id,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.patch("/findings/{finding_id}/status", response_model=FindingResponse)
async def update_finding_status_endpoint(
    finding_id: uuid.UUID,
    body: FindingStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FindingResponse:
    try:
        return await update_finding_status(
            db,
            current_user,
            finding_id,
            body.status,
            review_notes=body.review_notes,
            remediation_notes=body.remediation_notes,
            validation_notes=body.validation_notes,
        )
    except (FindingNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Finding not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MemberValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/findings/{finding_id}/assign", response_model=FindingResponse)
async def assign_finding_endpoint(
    finding_id: uuid.UUID,
    body: FindingAssignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FindingResponse:
    try:
        return await assign_finding(db, current_user, finding_id, body)
    except (FindingNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Finding not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
