from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
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
from app.services.investigation import InvestigationNotFoundError
from app.services.report import (
    ReportNotFoundError,
    create_report,
    get_report,
    list_reports,
)

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
    format: ReportDownloadFormat = Query(default="html"),  # noqa: A002
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        report = await get_report(db, current_user, report_id)
    except (ReportNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc

    if format == "html":
        content = report.html_content or ""
        media_type = "text/html; charset=utf-8"
        extension = "html"
    else:
        content = report.markdown_content or ""
        media_type = "text/markdown; charset=utf-8"
        extension = "md"
    filename = f"report-{report.id}.{extension}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
