from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.report import (
    ReportCreateRequest,
    ReportDetailResponse,
    ReportDownloadFormat,
    ReportListResponse,
    ReportResponse,
)
from app.services.audit import record_event
from app.services.investigation import ForbiddenError, InvestigationNotFoundError
from app.services.report import (
    ReportNotFoundError,
    create_report,
    get_report,
    list_reports,
)
from app.services.report_export import export_report

router = APIRouter(tags=["reports"])


@router.post(
    "/investigations/{investigation_id}/reports",
    response_model=ReportResponse,
)
async def create_report_endpoint(
    investigation_id: uuid.UUID,
    body: ReportCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    try:
        report = await create_report(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ReportResponse.model_validate(report)


@router.get(
    "/investigations/{investigation_id}/reports",
    response_model=ReportListResponse,
)
async def list_reports_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportListResponse:
    try:
        reports = await list_reports(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    return ReportListResponse(
        total=len(reports),
        items=[ReportResponse.model_validate(report) for report in reports],
    )


@router.get("/reports/{report_id}", response_model=ReportDetailResponse)
async def get_report_endpoint(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportDetailResponse:
    try:
        report = await get_report(db, current_user, report_id)
    except (ReportNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    return ReportDetailResponse.model_validate(report)


@router.get("/reports/{report_id}/download")
async def download_report_endpoint(
    report_id: uuid.UUID,
    request: Request,
    format: ReportDownloadFormat = Query(default="html"),  # noqa: A002
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        report = await get_report(db, current_user, report_id)
    except (ReportNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc

    exported = export_report(report, format)
    await record_event(
        db,
        action="report.downloaded",
        actor_id=current_user.id,
        resource_type="report",
        resource_id=report.id,
        investigation_id=report.investigation_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"format": format},
    )
    filename = f"report-{report.id}.{exported.extension}"
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
