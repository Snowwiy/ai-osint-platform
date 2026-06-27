from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_feature
from app.models.user import User
from app.schemas.report import (
    ReportActionResponse,
    ReportBulkGenerateRequest,
    ReportBulkGenerateResponse,
    ReportCreateRequest,
    ReportDetailResponse,
    ReportDownloadFormat,
    ReportingCenterResponse,
    ReportListResponse,
    ReportQualityResponse,
    ReportResponse,
    ReportSort,
    ReportStatus,
    ReportTemplateCreate,
    ReportTemplateListResponse,
    ReportTemplateResponse,
    ReportTemplateUpdate,
    ReportType,
)
from app.services.audit import record_event
from app.services.investigation import ForbiddenError, InvestigationNotFoundError
from app.services.governance import (
    FeatureDisabledError,
    ensure_export_format_allowed,
)
from app.services.report import (
    ReportNotFoundError,
    ReportTemplateNotFoundError,
    create_report,
    get_report,
    list_reports,
    report_quality_for_investigation,
)
from app.services.report_export import export_report
from app.services.reporting_center import (
    ReportTemplateValidationError,
    archive_report,
    bulk_generate_reports,
    create_report_template,
    deactivate_report_template,
    get_report_quality,
    list_report_templates,
    list_reporting_center_reports,
    restore_report,
    retry_failed_report,
    update_report_template,
)

router = APIRouter(tags=["reports"])


@router.get("/reports", response_model=ReportingCenterResponse)
async def reporting_center_endpoint(
    report_type: ReportType | None = Query(default=None),
    status_filter: ReportStatus | None = Query(default=None, alias="status"),
    report_format: ReportDownloadFormat | None = Query(
        default=None,
        alias="format",
    ),
    investigation_id: uuid.UUID | None = Query(default=None),
    generated_by: uuid.UUID | None = Query(default=None),
    archived: bool | None = Query(default=False),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    sort: ReportSort = Query(default="newest"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportingCenterResponse:
    try:
        return await list_reporting_center_reports(
            db,
            current_user,
            report_type=report_type,
            status=status_filter,
            report_format=report_format,
            investigation_id=investigation_id,
            generated_by=generated_by,
            archived=archived,
            start_date=start_date,
            end_date=end_date,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post(
    "/reports/bulk-generate",
    response_model=ReportBulkGenerateResponse,
)
async def bulk_generate_reports_endpoint(
    body: ReportBulkGenerateRequest,
    _feature: None = Depends(require_feature("enable_report_exports")),
    _bulk_feature: None = Depends(require_feature("enable_bulk_actions")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportBulkGenerateResponse:
    try:
        await ensure_export_format_allowed(db, body.output_format)
        return await bulk_generate_reports(db, current_user, body)
    except FeatureDisabledError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "feature_disabled", "message": str(exc)},
        ) from exc


@router.get(
    "/report-templates",
    response_model=ReportTemplateListResponse,
)
async def list_report_templates_endpoint(
    include_inactive: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportTemplateListResponse:
    return await list_report_templates(
        db,
        current_user,
        include_inactive=include_inactive,
    )


@router.post(
    "/report-templates",
    response_model=ReportTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_report_template_endpoint(
    body: ReportTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportTemplateResponse:
    try:
        template = await create_report_template(db, current_user, body)
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ReportTemplateValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReportTemplateResponse.model_validate(template)


@router.patch(
    "/report-templates/{template_id}",
    response_model=ReportTemplateResponse,
)
async def update_report_template_endpoint(
    template_id: uuid.UUID,
    body: ReportTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportTemplateResponse:
    try:
        template = await update_report_template(
            db,
            current_user,
            template_id,
            body,
        )
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ReportTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportTemplateValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReportTemplateResponse.model_validate(template)


@router.delete(
    "/report-templates/{template_id}",
    response_model=ReportTemplateResponse,
)
async def deactivate_report_template_endpoint(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportTemplateResponse:
    try:
        template = await deactivate_report_template(
            db,
            current_user,
            template_id,
        )
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ReportTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportTemplateValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReportTemplateResponse.model_validate(template)


@router.get(
    "/investigations/{investigation_id}/reports/quality",
    response_model=ReportQualityResponse,
)
async def investigation_report_quality_endpoint(
    investigation_id: uuid.UUID,
    report_type: ReportType = Query(default="technical"),
    template_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportQualityResponse:
    try:
        return await report_quality_for_investigation(
            db,
            current_user,
            investigation_id,
            report_type=report_type,
            template_id=template_id,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ReportTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/investigations/{investigation_id}/reports",
    response_model=ReportResponse,
)
async def create_report_endpoint(
    investigation_id: uuid.UUID,
    body: ReportCreateRequest,
    request: Request,
    _feature: None = Depends(require_feature("enable_report_exports")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    try:
        await ensure_export_format_allowed(db, body.output_format)
        report = await create_report(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ReportTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FeatureDisabledError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "feature_disabled", "message": str(exc)},
        ) from exc
    await record_event(
        db,
        action="report.generated" if report.status == "ready" else "report.failed",
        actor_id=current_user.id,
        resource_type="report",
        resource_id=report.id,
        investigation_id=report.investigation_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={
            "report_type": report.report_type,
            "status": report.status,
            "template_id": str(report.template_id) if report.template_id else None,
        },
    )
    return ReportResponse.model_validate(report)


@router.get(
    "/investigations/{investigation_id}/reports",
    response_model=ReportListResponse,
)
async def list_reports_endpoint(
    investigation_id: uuid.UUID,
    include_archived: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportListResponse:
    try:
        reports = await list_reports(
            db,
            current_user,
            investigation_id,
            include_archived=include_archived,
        )
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


@router.patch(
    "/reports/{report_id}/archive",
    response_model=ReportActionResponse,
)
async def archive_report_endpoint(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportActionResponse:
    try:
        report = await archive_report(db, current_user, report_id)
    except (ReportNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ReportActionResponse(
        report=ReportResponse.model_validate(report),
        message="Report archived.",
    )


@router.patch(
    "/reports/{report_id}/restore",
    response_model=ReportActionResponse,
)
async def restore_report_endpoint(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportActionResponse:
    try:
        report = await restore_report(db, current_user, report_id)
    except (ReportNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ReportActionResponse(
        report=ReportResponse.model_validate(report),
        message="Report restored.",
    )


@router.post(
    "/reports/{report_id}/retry",
    response_model=ReportActionResponse,
)
async def retry_report_endpoint(
    report_id: uuid.UUID,
    _feature: None = Depends(require_feature("enable_report_exports")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportActionResponse:
    try:
        report_for_format = await get_report(db, current_user, report_id)
        await ensure_export_format_allowed(db, report_for_format.report_format)
        report = await retry_failed_report(db, current_user, report_id)
    except (ReportNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ReportTemplateValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FeatureDisabledError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "feature_disabled", "message": str(exc)},
        ) from exc
    return ReportActionResponse(
        report=ReportResponse.model_validate(report),
        message="Report retry completed.",
    )


@router.get(
    "/reports/{report_id}/quality",
    response_model=ReportQualityResponse,
)
async def report_quality_endpoint(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportQualityResponse:
    try:
        return await get_report_quality(db, current_user, report_id)
    except (ReportNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    except ReportTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/reports/{report_id}/download")
async def download_report_endpoint(
    report_id: uuid.UUID,
    request: Request,
    format: ReportDownloadFormat = Query(default="html"),  # noqa: A002
    _feature: None = Depends(require_feature("enable_report_exports")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await ensure_export_format_allowed(db, format)
        report = await get_report(db, current_user, report_id)
    except (ReportNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    except FeatureDisabledError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "feature_disabled", "message": str(exc)},
        ) from exc

    if report.status not in {"ready", "archived"}:
        raise HTTPException(
            status_code=409,
            detail="Report is not ready for download",
        )
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
    if report.report_type == "executive":
        await record_event(
            db,
            action="executive.report_exported",
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
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
