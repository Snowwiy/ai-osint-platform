from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.case_review import (
    CaseCloseRequest,
    CaseReviewDecisionRequest,
    CaseReviewResponse,
    CaseReviewSubmitRequest,
    EvidenceCompletenessResponse,
    RemediationValidationDecisionRequest,
    RemediationValidationResponse,
    RemediationValidationSubmitRequest,
    ReportApprovalDecisionRequest,
    ReportApprovalResponse,
    ReportApprovalSubmitRequest,
    ReviewBoardResponse,
)
from app.services.case_review import (
    CaseReviewValidationError,
    close_case,
    decide_case_review,
    decide_remediation_validation,
    decide_report_approval,
    get_case_review,
    get_evidence_completeness,
    get_review_board,
    submit_case_review,
    submit_remediation_validation,
    submit_report_approval,
)
from app.services.intelligence.findings_service import FindingNotFoundError
from app.services.investigation import ForbiddenError, InvestigationNotFoundError
from app.services.report import ReportNotFoundError

router = APIRouter(tags=["case-review"])


@router.get(
    "/investigations/{investigation_id}/review",
    response_model=CaseReviewResponse,
)
async def get_case_review_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseReviewResponse:
    try:
        return await get_case_review(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post(
    "/investigations/{investigation_id}/review/submit",
    response_model=CaseReviewResponse,
)
async def submit_case_review_endpoint(
    investigation_id: uuid.UUID,
    body: CaseReviewSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseReviewResponse:
    try:
        return await submit_case_review(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseReviewValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/investigations/{investigation_id}/review/decision",
    response_model=CaseReviewResponse,
)
async def decide_case_review_endpoint(
    investigation_id: uuid.UUID,
    body: CaseReviewDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseReviewResponse:
    try:
        return await decide_case_review(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseReviewValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/investigations/{investigation_id}/close",
    response_model=CaseReviewResponse,
)
async def close_case_endpoint(
    investigation_id: uuid.UUID,
    body: CaseCloseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseReviewResponse:
    try:
        return await close_case(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseReviewValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/investigations/{investigation_id}/completeness",
    response_model=EvidenceCompletenessResponse,
)
async def investigation_completeness_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceCompletenessResponse:
    try:
        return await get_evidence_completeness(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post(
    "/reports/{report_id}/submit-approval",
    response_model=ReportApprovalResponse,
)
async def submit_report_approval_endpoint(
    report_id: uuid.UUID,
    body: ReportApprovalSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportApprovalResponse:
    try:
        return await submit_report_approval(db, current_user, report_id, body)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseReviewValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/reports/{report_id}/approval-decision",
    response_model=ReportApprovalResponse,
)
async def decide_report_approval_endpoint(
    report_id: uuid.UUID,
    body: ReportApprovalDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportApprovalResponse:
    try:
        return await decide_report_approval(db, current_user, report_id, body)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    except (InvestigationNotFoundError, ForbiddenError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseReviewValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/findings/{finding_id}/validation/submit",
    response_model=RemediationValidationResponse,
)
async def submit_remediation_validation_endpoint(
    finding_id: uuid.UUID,
    body: RemediationValidationSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RemediationValidationResponse:
    try:
        return await submit_remediation_validation(db, current_user, finding_id, body)
    except (FindingNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Finding not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseReviewValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/findings/{finding_id}/validation/decision",
    response_model=RemediationValidationResponse,
)
async def decide_remediation_validation_endpoint(
    finding_id: uuid.UUID,
    body: RemediationValidationDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RemediationValidationResponse:
    try:
        return await decide_remediation_validation(db, current_user, finding_id, body)
    except (FindingNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Finding not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseReviewValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/review-board", response_model=ReviewBoardResponse)
async def review_board_endpoint(
    status_filter: str | None = Query(default=None, alias="status"),
    assigned_reviewer: uuid.UUID | None = Query(default=None),
    priority: str | None = Query(default=None),
    risk: str | None = Query(default=None),
    due_date_before: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewBoardResponse:
    return await get_review_board(
        db,
        current_user,
        status=status_filter,
        assigned_reviewer=assigned_reviewer,
        priority=priority,
        risk=risk,
        due_date_before=due_date_before,
    )
