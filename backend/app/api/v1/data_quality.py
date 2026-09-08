from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from app.schemas.data_quality import (
    DataQualityEntityType,
    DataQualityIssueListResponse,
    DataQualityIssueResponse,
    DataQualityOverviewResponse,
    DataQualityScanResponse,
    DataQualitySeverity,
    DataQualityStatus,
    MaintenanceDryRunResponse,
    StaleNotificationArchiveRequest,
    StaleNotificationArchiveResponse,
)
from app.services.data_quality import (
    DataQualityIssueNotFoundError,
    InvalidIssueTransitionError,
    archive_stale_notifications,
    build_maintenance_dry_run,
    get_quality_issue,
    get_quality_overview,
    list_quality_issues,
    run_quality_scan,
    to_issue_response,
    transition_quality_issue,
)

router = APIRouter(prefix="/admin", tags=["data-quality"])


@router.get("/data-quality/overview", response_model=DataQualityOverviewResponse)
async def data_quality_overview_endpoint(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> DataQualityOverviewResponse:
    return await get_quality_overview(db)


@router.post("/data-quality/run", response_model=DataQualityScanResponse)
async def run_data_quality_endpoint(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> DataQualityScanResponse:
    return await run_quality_scan(db, current_user)


@router.get("/data-quality/issues", response_model=DataQualityIssueListResponse)
async def list_data_quality_issues_endpoint(
    severity: DataQualitySeverity | None = Query(default=None),
    status: DataQualityStatus | None = Query(default=None),
    issue_type: str | None = Query(default=None, min_length=1, max_length=100),
    entity_type: DataQualityEntityType | None = Query(default=None),
    investigation_id: uuid.UUID | None = Query(default=None),
    engagement_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> DataQualityIssueListResponse:
    total, issues = await list_quality_issues(
        db,
        severity=severity,
        status=status,
        issue_type=issue_type,
        entity_type=entity_type,
        investigation_id=investigation_id,
        engagement_id=engagement_id,
        limit=limit,
        offset=offset,
    )
    return DataQualityIssueListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[to_issue_response(issue) for issue in issues],
    )


@router.get(
    "/data-quality/issues/{issue_id}", response_model=DataQualityIssueResponse
)
async def get_data_quality_issue_endpoint(
    issue_id: uuid.UUID,
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> DataQualityIssueResponse:
    try:
        issue = await get_quality_issue(db, issue_id)
    except DataQualityIssueNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Data quality issue not found.") from exc
    return to_issue_response(issue)


@router.patch(
    "/data-quality/issues/{issue_id}/acknowledge",
    response_model=DataQualityIssueResponse,
)
async def acknowledge_data_quality_issue_endpoint(
    issue_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> DataQualityIssueResponse:
    return await _transition_issue(db, current_user, issue_id, "acknowledged")


@router.patch(
    "/data-quality/issues/{issue_id}/ignore",
    response_model=DataQualityIssueResponse,
)
async def ignore_data_quality_issue_endpoint(
    issue_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> DataQualityIssueResponse:
    return await _transition_issue(db, current_user, issue_id, "ignored")


@router.patch(
    "/data-quality/issues/{issue_id}/resolve",
    response_model=DataQualityIssueResponse,
)
async def resolve_data_quality_issue_endpoint(
    issue_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> DataQualityIssueResponse:
    return await _transition_issue(db, current_user, issue_id, "resolved")


@router.get("/maintenance/overview", response_model=DataQualityOverviewResponse)
async def maintenance_overview_endpoint(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> DataQualityOverviewResponse:
    return await get_quality_overview(db)


@router.post("/maintenance/dry-run", response_model=MaintenanceDryRunResponse)
async def maintenance_dry_run_endpoint(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceDryRunResponse:
    return await build_maintenance_dry_run(db, current_user)


@router.post(
    "/maintenance/archive-stale-notifications",
    response_model=StaleNotificationArchiveResponse,
)
async def archive_stale_notifications_endpoint(
    body: StaleNotificationArchiveRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> StaleNotificationArchiveResponse:
    return await archive_stale_notifications(
        db,
        current_user,
        older_than_days=body.older_than_days,
    )


async def _transition_issue(
    db: AsyncSession,
    current_user: User,
    issue_id: uuid.UUID,
    status: DataQualityStatus,
) -> DataQualityIssueResponse:
    try:
        issue = await transition_quality_issue(db, current_user, issue_id, status)
    except DataQualityIssueNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Data quality issue not found.") from exc
    except InvalidIssueTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return to_issue_response(issue)
