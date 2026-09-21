from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import (
    get_current_user,
    get_db,
    require_feature,
    require_role,
)
from app.models.background_job import BackgroundJob, BackgroundJobEvent
from app.models.user import User
from app.schemas.investigation import InvestigationPriority
from app.schemas.operations import (
    AnalystWorkloadResponse,
    DashboardHighlightsResponse,
    DashboardOverviewResponse,
    DashboardTimelineResponse,
    DashboardTriageResponse,
    InvestigationBulkRequest,
    InvestigationBulkResponse,
    InvestigationPinResponse,
    InvestigationPinUpdate,
    InvestigationQueueResponse,
    QueueSort,
    QueueStatusFilter,
    RiskFilter,
)
from app.schemas.operations_center import (
    EnvironmentValidationResponse,
    ExportFormat,
    OperationsStatusResponse,
    RestoreValidationRequest,
    RestoreValidationResponse,
)
from app.services.audit import record_event
from app.services.background_jobs import (
    JobValidationError,
    queue_counts,
    request_cancellation,
)
from app.services.investigation import ForbiddenError, InvestigationNotFoundError
from app.services.operations import (
    OperationsValidationError,
    apply_investigation_bulk_action,
    get_analyst_workload,
    get_dashboard_highlights,
    get_dashboard_overview,
    get_dashboard_timeline,
    get_dashboard_triage,
    get_investigation_queue,
    set_investigation_pin,
)
from app.services.operations_center import (
    build_backup_package,
    build_diagnostics_package,
    get_environment_validation,
    get_operations_status,
    package_to_zip,
    validate_restore_payload,
)

router = APIRouter(tags=["operations"])


def _job_view(job: BackgroundJob) -> dict[str, Any]:
    retryable = (
        job.status == "failed"
        and job.attempt_count < job.max_attempts
        and job.last_error_code not in {
            "invalid_payload", "validation", "unsupported_job", "authorization",
            "configuration",
        }
    )
    return {
        "id": str(job.id),
        "type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "scheduled_at": job.scheduled_at,
        "next_retry_at": job.next_retry_at,
        "attempts": job.attempt_count,
        "max_attempts": job.max_attempts,
        "requested_by": str(job.requested_by_user_id)
        if job.requested_by_user_id
        else None,
        "investigation_id": str(job.investigation_id) if job.investigation_id else None,
        "asset_id": str(job.asset_id) if job.asset_id else None,
        "worker": job.worker_id,
        "last_safe_error": job.last_error_summary,
        "result_summary": job.result_summary,
        "can_retry": retryable,
        "can_cancel": job.status in {"queued", "scheduled", "retry_wait", "running"},
    }


@router.get("/operations/background-jobs")
async def background_jobs_endpoint(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    jobs = (
        (
            await db.execute(
                select(BackgroundJob)
                .order_by(BackgroundJob.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return {
        "backend": settings.BACKGROUND_JOB_BACKEND,
        "counts": await queue_counts(db),
        "jobs": [_job_view(job) for job in jobs],
    }


@router.post("/operations/background-jobs/{job_id}/cancel")
async def cancel_background_job_endpoint(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    job = (
        await db.execute(
            select(BackgroundJob).where(BackgroundJob.id == job_id).with_for_update()
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    try:
        await request_cancellation(db, job, current_user.id)
    except JobValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _job_view(job)


@router.post("/operations/background-jobs/{job_id}/retry")
async def retry_background_job_endpoint(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    job = (
        await db.execute(
            select(BackgroundJob).where(BackgroundJob.id == job_id).with_for_update()
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not _job_view(job)["can_retry"]:
        raise HTTPException(status_code=409, detail="Job is not eligible for retry.")
    job.status = "queued"
    job.scheduled_at = datetime.now(UTC)
    job.next_retry_at = None
    db.add(
        BackgroundJobEvent(
            job_id=job.id,
            event_type="retry_scheduled",
            detail="Operator queued a bounded retry.",
        )
    )
    await record_event(
        db,
        action="background_job.retry",
        actor_id=current_user.id,
        resource_type="background_job",
        resource_id=job.id,
        metadata={"job_type": job.job_type},
    )
    return _job_view(job)


@router.get("/operations/status", response_model=OperationsStatusResponse)
async def operations_status_endpoint(
    request: Request,
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> OperationsStatusResponse:
    return await get_operations_status(db, request.app.state.redis)


@router.get("/operations/environment", response_model=EnvironmentValidationResponse)
async def operations_environment_endpoint(
    _current_user: User = Depends(require_role("admin")),
) -> EnvironmentValidationResponse:
    return await get_environment_validation()


@router.get("/operations/diagnostics")
async def operations_diagnostics_endpoint(
    request: Request,
    format: ExportFormat = Query(default="json"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    package = await build_diagnostics_package(db, request.app.state.redis)
    await record_event(
        db,
        action="diagnostics.generated",
        actor_id=current_user.id,
        resource_type="operations",
        metadata={"format": format},
    )
    await db.commit()
    return _export_response(
        filename=f"raventech-diagnostics.{format}",
        payload=jsonable_encoder(package),
        format=format,
        zip_entry_name="diagnostics.json",
    )


@router.get("/operations/backup")
async def operations_backup_endpoint(
    format: ExportFormat = Query(default="json"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    package = await build_backup_package(db)
    await record_event(
        db,
        action="data.exported",
        actor_id=current_user.id,
        resource_type="operations_backup",
        metadata={"format": format, "contains_secrets": False},
    )
    await db.commit()
    return _export_response(
        filename=f"raventech-backup.{format}",
        payload=jsonable_encoder(package),
        format=format,
        zip_entry_name="backup.json",
    )


@router.post(
    "/operations/restore/validate",
    response_model=RestoreValidationResponse,
)
async def operations_restore_validate_endpoint(
    body: RestoreValidationRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> RestoreValidationResponse:
    result = validate_restore_payload(body)
    await record_event(
        db,
        action="restore.validated",
        actor_id=current_user.id,
        resource_type="operations_backup",
        metadata={
            "valid": result.valid,
            "compatible": result.compatible,
            "dry_run": True,
        },
    )
    await db.commit()
    return result


@router.get("/dashboard/highlights", response_model=DashboardHighlightsResponse)
async def dashboard_highlights_endpoint(
    _feature: None = Depends(require_feature("enable_advanced_dashboard")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardHighlightsResponse:
    return await get_dashboard_highlights(db, current_user)


@router.get("/dashboard/overview", response_model=DashboardOverviewResponse)
async def dashboard_overview_endpoint(
    _feature: None = Depends(require_feature("enable_advanced_dashboard")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardOverviewResponse:
    return await get_dashboard_overview(db, current_user)


@router.get("/dashboard/triage", response_model=DashboardTriageResponse)
async def dashboard_triage_endpoint(
    _feature: None = Depends(require_feature("enable_advanced_dashboard")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardTriageResponse:
    return await get_dashboard_triage(db, current_user)


@router.get("/dashboard/timeline", response_model=DashboardTimelineResponse)
async def dashboard_timeline_endpoint(
    actor_id: uuid.UUID | None = Query(default=None),
    investigation_id: uuid.UUID | None = Query(default=None),
    event_type: str | None = Query(default=None, max_length=100),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _feature: None = Depends(require_feature("enable_advanced_dashboard")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardTimelineResponse:
    try:
        return await get_dashboard_timeline(
            db,
            current_user,
            actor_id=actor_id,
            investigation_id=investigation_id,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.get("/investigations/queue", response_model=InvestigationQueueResponse)
async def investigation_queue_endpoint(
    status: QueueStatusFilter | None = Query(default=None),
    priority: InvestigationPriority | None = Query(default=None),
    assigned_analyst: uuid.UUID | None = Query(default=None),
    tag: uuid.UUID | None = Query(default=None),
    risk_level: RiskFilter | None = Query(default=None),
    sort: QueueSort = Query(default="highest_risk"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationQueueResponse:
    return await get_investigation_queue(
        db,
        current_user,
        status=status,
        priority=priority,
        assigned_analyst=assigned_analyst,
        tag_id=tag,
        risk_level=risk_level,
        sort=sort,
        skip=skip,
        limit=limit,
    )


@router.post("/investigations/bulk", response_model=InvestigationBulkResponse)
async def investigation_bulk_endpoint(
    body: InvestigationBulkRequest,
    _feature: None = Depends(require_feature("enable_bulk_actions")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationBulkResponse:
    return await apply_investigation_bulk_action(db, current_user, body)


@router.patch(
    "/investigations/{investigation_id}/pin",
    response_model=InvestigationPinResponse,
)
async def investigation_pin_endpoint(
    investigation_id: uuid.UUID,
    body: InvestigationPinUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationPinResponse:
    try:
        return await set_investigation_pin(
            db,
            current_user,
            investigation_id,
            pinned=body.pinned,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OperationsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/analytics/analysts", response_model=AnalystWorkloadResponse)
async def analyst_workload_endpoint(
    _feature: None = Depends(require_feature("enable_advanced_dashboard")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalystWorkloadResponse:
    return await get_analyst_workload(db, current_user)


def _export_response(
    *,
    filename: str,
    payload: dict[str, Any],
    format: ExportFormat,
    zip_entry_name: str,
) -> Response:
    if format == "zip":
        content = package_to_zip(zip_entry_name, payload)
        media_type = "application/zip"
    else:
        content = json.dumps(payload, indent=2).encode("utf-8")
        media_type = "application/json"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
