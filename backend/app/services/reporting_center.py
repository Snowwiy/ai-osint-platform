from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.report import Report
from app.models.report_template import ReportTemplate
from app.models.user import User
from app.schemas.report import (
    ReportBulkGenerateRequest,
    ReportBulkGenerateResponse,
    ReportBulkResult,
    ReportCreateRequest,
    ReportDownloadFormat,
    ReportingCenterItem,
    ReportingCenterResponse,
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
from app.services.investigation import (
    CASE_ADMIN_ROLES,
    ForbiddenError,
    InvestigationNotFoundError,
    ensure_investigation_permission,
    get_investigation,
)
from app.services.report import (
    ReportTemplateNotFoundError,
    create_report,
    get_report,
    report_quality_for_investigation,
    retry_report_generation,
)

logger = logging.getLogger(__name__)


class ReportTemplateValidationError(Exception):
    pass


async def list_reporting_center_reports(
    db: AsyncSession,
    user: User,
    *,
    report_type: ReportType | None = None,
    status: ReportStatus | None = None,
    report_format: ReportDownloadFormat | None = None,
    investigation_id: uuid.UUID | None = None,
    generated_by: uuid.UUID | None = None,
    archived: bool | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    sort: ReportSort = "newest",
    limit: int = 50,
    offset: int = 0,
) -> ReportingCenterResponse:
    investigations = await _accessible_investigations(db, user)
    accessible_ids = {investigation.id for investigation in investigations}
    if investigation_id is not None and investigation_id not in accessible_ids:
        raise InvestigationNotFoundError("Investigation not found")
    if not accessible_ids:
        return ReportingCenterResponse(total=0, limit=limit, offset=offset, items=[])
    statement = select(Report).where(Report.investigation_id.in_(accessible_ids))
    if report_type is not None:
        statement = statement.where(Report.report_type == report_type)
    if status is not None:
        statement = statement.where(Report.status == status)
    if report_format is not None:
        statement = statement.where(Report.report_format == report_format)
    if investigation_id is not None:
        statement = statement.where(Report.investigation_id == investigation_id)
    if generated_by is not None:
        statement = statement.where(Report.generated_by == generated_by)
    if archived is True:
        statement = statement.where(Report.status == "archived")
    elif archived is False:
        statement = statement.where(Report.status != "archived")
    if start_date is not None:
        statement = statement.where(Report.created_at >= start_date)
    if end_date is not None:
        statement = statement.where(Report.created_at <= end_date)
    result = await db.execute(statement)
    reports = list(result.scalars().all())
    ordered = _sort_reports(
        reports,
        sort,
        {investigation.id: investigation.title for investigation in investigations},
    )
    page = ordered[offset : offset + limit]
    users = await _users_by_id(
        db,
        {report.generated_by for report in page if report.generated_by is not None},
    )
    templates = await _templates_by_id(
        db,
        {report.template_id for report in page if report.template_id is not None},
    )
    investigation_titles = {
        investigation.id: investigation.title for investigation in investigations
    }
    return ReportingCenterResponse(
        total=len(ordered),
        limit=limit,
        offset=offset,
        items=[
            ReportingCenterItem(
                **ReportResponse.model_validate(report).model_dump(),
                investigation_title=investigation_titles.get(
                    report.investigation_id,
                    "Unknown investigation",
                ),
                generated_by_name=(
                    users[report.generated_by].username
                    if report.generated_by in users
                    else None
                ),
                template_name=(
                    templates[report.template_id].name
                    if report.template_id in templates
                    else None
                ),
            )
            for report in page
        ],
    )


async def list_report_templates(
    db: AsyncSession,
    user: User,
    *,
    include_inactive: bool = False,
) -> ReportTemplateListResponse:
    statement = select(ReportTemplate)
    if not include_inactive or user.role != "admin":
        statement = statement.where(ReportTemplate.is_active.is_(True))
    result = await db.execute(
        statement.order_by(
            ReportTemplate.report_type,
            ReportTemplate.name,
        )
    )
    templates = list(result.scalars().all())
    return ReportTemplateListResponse(
        total=len(templates),
        items=[
            ReportTemplateResponse.model_validate(template)
            for template in templates
        ],
    )


async def create_report_template(
    db: AsyncSession,
    user: User,
    body: ReportTemplateCreate,
) -> ReportTemplate:
    _require_platform_admin(user)
    await _ensure_unique_template_name(db, body.name)
    if body.is_default:
        await _clear_default_template(db, body.report_type)
    template = ReportTemplate(
        name=body.name,
        description=body.description,
        report_type=body.report_type,
        sections=list(body.sections),
        is_default=body.is_default,
        is_active=body.is_active,
        created_by=user.id,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    await record_event(
        db,
        action="report_template.created",
        actor_id=user.id,
        resource_type="report_template",
        resource_id=template.id,
        metadata=template.metadata_summary,
    )
    return template


async def update_report_template(
    db: AsyncSession,
    user: User,
    template_id: uuid.UUID,
    body: ReportTemplateUpdate,
) -> ReportTemplate:
    _require_platform_admin(user)
    template = await db.get(ReportTemplate, template_id)
    if template is None:
        raise ReportTemplateNotFoundError("Report template not found")
    original_report_type = template.report_type
    if body.name is not None and body.name != template.name:
        await _ensure_unique_template_name(db, body.name)
        template.name = body.name
    if body.description is not None:
        template.description = body.description
    if body.report_type is not None:
        template.report_type = body.report_type
    if body.sections is not None:
        template.sections = list(body.sections)
    if body.is_active is not None:
        template.is_active = body.is_active
    report_type_changed = (
        body.report_type is not None and body.report_type != original_report_type
    )
    if body.is_default is not None:
        if body.is_default:
            await _clear_default_template(db, template.report_type)
        template.is_default = body.is_default
    elif report_type_changed and template.is_default:
        await _clear_default_template(db, template.report_type)
        template.is_default = True
    db.add(template)
    await db.flush()
    await db.refresh(template)
    await record_event(
        db,
        action="report_template.updated",
        actor_id=user.id,
        resource_type="report_template",
        resource_id=template.id,
        metadata=template.metadata_summary,
    )
    return template


async def deactivate_report_template(
    db: AsyncSession,
    user: User,
    template_id: uuid.UUID,
) -> ReportTemplate:
    _require_platform_admin(user)
    template = await db.get(ReportTemplate, template_id)
    if template is None:
        raise ReportTemplateNotFoundError("Report template not found")
    if template.created_by is None:
        raise ReportTemplateValidationError(
            "Built-in report templates cannot be removed"
        )
    if not template.is_active:
        return template
    template.is_active = False
    template.is_default = False
    db.add(template)
    await db.flush()
    await db.refresh(template)
    await record_event(
        db,
        action="report_template.deactivated",
        actor_id=user.id,
        resource_type="report_template",
        resource_id=template.id,
        metadata=template.metadata_summary,
    )
    return template


async def archive_report(
    db: AsyncSession,
    user: User,
    report_id: uuid.UUID,
) -> Report:
    report = await get_report(db, user, report_id)
    await ensure_investigation_permission(
        db,
        user,
        report.investigation_id,
        CASE_ADMIN_ROLES,
        "Only investigation owners or admins can archive reports",
    )
    if report.status == "archived":
        return report
    report.report_metadata = {
        **report.report_metadata,
        "status_before_archive": report.status,
    }
    report.status = "archived"
    report.archived_at = datetime.now(UTC)
    report.progress_label = "Archived"
    db.add(report)
    await db.flush()
    await db.refresh(report)
    await record_event(
        db,
        action="report.archived",
        actor_id=user.id,
        resource_type="report",
        resource_id=report.id,
        investigation_id=report.investigation_id,
    )
    await record_event(
        db,
        action="archive.created",
        actor_id=user.id,
        resource_type="report",
        resource_id=report.id,
        investigation_id=report.investigation_id,
    )
    return report


async def restore_report(
    db: AsyncSession,
    user: User,
    report_id: uuid.UUID,
) -> Report:
    report = await get_report(db, user, report_id)
    await ensure_investigation_permission(
        db,
        user,
        report.investigation_id,
        CASE_ADMIN_ROLES,
        "Only investigation owners or admins can restore reports",
    )
    if report.status != "archived":
        return report
    previous_status = report.report_metadata.get("status_before_archive")
    report.status = (
        str(previous_status)
        if previous_status in {"ready", "failed"}
        else "ready"
    )
    report.archived_at = None
    report.progress_label = (
        "Ready to download" if report.status == "ready" else "Generation failed"
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)
    await record_event(
        db,
        action="report.restored",
        actor_id=user.id,
        resource_type="report",
        resource_id=report.id,
        investigation_id=report.investigation_id,
    )
    await record_event(
        db,
        action="archive.restored",
        actor_id=user.id,
        resource_type="report",
        resource_id=report.id,
        investigation_id=report.investigation_id,
    )
    return report


async def retry_failed_report(
    db: AsyncSession,
    user: User,
    report_id: uuid.UUID,
) -> Report:
    report = await get_report(db, user, report_id)
    if report.status != "failed":
        raise ReportTemplateValidationError("Only failed reports can be retried")
    report = await retry_report_generation(db, user, report)
    await record_event(
        db,
        action="report.retried",
        actor_id=user.id,
        resource_type="report",
        resource_id=report.id,
        investigation_id=report.investigation_id,
        metadata={"retry_count": report.retry_count, "status": report.status},
    )
    if report.status == "ready":
        await record_event(
            db,
            action="report.generated",
            actor_id=user.id,
            resource_type="report",
            resource_id=report.id,
            investigation_id=report.investigation_id,
            metadata={"retry": True},
        )
    else:
        await record_event(
            db,
            action="report.failed",
            actor_id=user.id,
            resource_type="report",
            resource_id=report.id,
            investigation_id=report.investigation_id,
            metadata={"retry": True},
        )
    return report


async def get_report_quality(
    db: AsyncSession,
    user: User,
    report_id: uuid.UUID,
) -> ReportQualityResponse:
    report = await get_report(db, user, report_id)
    return await report_quality_for_investigation(
        db,
        user,
        report.investigation_id,
        report_type=report.report_type,
        template_id=report.template_id,
        report_id=report.id,
    )


async def bulk_generate_reports(
    db: AsyncSession,
    user: User,
    body: ReportBulkGenerateRequest,
) -> ReportBulkGenerateResponse:
    results: list[ReportBulkResult] = []
    for investigation_id in body.investigation_ids:
        try:
            async with db.begin_nested():
                await get_investigation(db, user, investigation_id)
                await ensure_investigation_permission(
                    db,
                    user,
                    investigation_id,
                    CASE_ADMIN_ROLES,
                    "Bulk report generation requires owner or admin access",
                )
                report = await create_report(
                    db,
                    user,
                    investigation_id,
                    body=_bulk_create_request(body),
                )
                result_status: Literal["generated", "failed"] = (
                    "generated" if report.status == "ready" else "failed"
                )
                results.append(
                    ReportBulkResult(
                        investigation_id=investigation_id,
                        report_id=report.id,
                        status=result_status,
                        detail=(
                            "Report generated."
                            if result_status == "generated"
                            else report.failure_reason or "Report generation failed."
                        ),
                    )
                )
                await record_event(
                    db,
                    action=(
                        "report.generated"
                        if result_status == "generated"
                        else "report.failed"
                    ),
                    actor_id=user.id,
                    resource_type="report",
                    resource_id=report.id,
                    investigation_id=investigation_id,
                    metadata={"bulk": True, "report_type": body.report_type},
                )
        except (InvestigationNotFoundError, ForbiddenError) as exc:
            results.append(
                ReportBulkResult(
                    investigation_id=investigation_id,
                    status="skipped",
                    detail=str(exc),
                )
            )
        except (ReportTemplateNotFoundError, ReportTemplateValidationError) as exc:
            results.append(
                ReportBulkResult(
                    investigation_id=investigation_id,
                    status="failed",
                    detail=str(exc),
                )
            )
        except Exception as exc:
            logger.warning(
                "Bulk report generation failed for %s: %s",
                investigation_id,
                exc,
            )
            results.append(
                ReportBulkResult(
                    investigation_id=investigation_id,
                    status="failed",
                    detail="Report generation could not complete.",
                )
            )
    generated = sum(item.status == "generated" for item in results)
    skipped = sum(item.status == "skipped" for item in results)
    failed = sum(item.status == "failed" for item in results)
    await record_event(
        db,
        action="report.bulk_generated",
        actor_id=user.id,
        resource_type="report",
        metadata={
            "report_type": body.report_type,
            "generated": generated,
            "skipped": skipped,
            "failed": failed,
        },
    )
    return ReportBulkGenerateResponse(
        generated=generated,
        skipped=skipped,
        failed=failed,
        results=results,
    )


async def _accessible_investigations(
    db: AsyncSession,
    user: User,
) -> list[Investigation]:
    if user.role == "admin":
        result = await db.execute(select(Investigation))
    else:
        result = await db.execute(
            select(Investigation)
            .join(
                InvestigationMember,
                InvestigationMember.investigation_id == Investigation.id,
            )
            .where(InvestigationMember.user_id == user.id)
        )
    return list(result.scalars().unique().all())


def _sort_reports(
    reports: list[Report],
    sort: ReportSort,
    investigation_titles: dict[uuid.UUID, str],
) -> list[Report]:
    if sort == "oldest":
        return sorted(reports, key=lambda report: report.created_at)
    if sort == "status":
        return sorted(
            reports,
            key=lambda report: (
                report.status,
                -report.created_at.timestamp(),
            ),
        )
    if sort == "report_type":
        return sorted(
            reports,
            key=lambda report: (report.report_type, -report.created_at.timestamp()),
        )
    if sort == "investigation":
        return sorted(
            reports,
            key=lambda report: (
                investigation_titles.get(report.investigation_id, "").lower(),
                -report.created_at.timestamp(),
            ),
        )
    return sorted(reports, key=lambda report: report.created_at, reverse=True)


async def _users_by_id(
    db: AsyncSession,
    user_ids: set[uuid.UUID],
) -> dict[uuid.UUID, User]:
    if not user_ids:
        return {}
    result = await db.execute(select(User).where(User.id.in_(user_ids)))
    return {user.id: user for user in result.scalars().all()}


async def _templates_by_id(
    db: AsyncSession,
    template_ids: set[uuid.UUID],
) -> dict[uuid.UUID, ReportTemplate]:
    if not template_ids:
        return {}
    result = await db.execute(
        select(ReportTemplate).where(ReportTemplate.id.in_(template_ids))
    )
    return {template.id: template for template in result.scalars().all()}


async def _ensure_unique_template_name(db: AsyncSession, name: str) -> None:
    result = await db.execute(
        select(ReportTemplate.id).where(ReportTemplate.name == name)
    )
    if result.scalar_one_or_none() is not None:
        raise ReportTemplateValidationError(
            "A report template with this name already exists"
        )


async def _clear_default_template(db: AsyncSession, report_type: str) -> None:
    result = await db.execute(
        select(ReportTemplate).where(
            ReportTemplate.report_type == report_type,
            ReportTemplate.is_default.is_(True),
        )
    )
    for template in result.scalars().all():
        template.is_default = False
        db.add(template)


def _require_platform_admin(user: User) -> None:
    if user.role != "admin":
        raise ForbiddenError("Platform administrator access is required")


def _bulk_create_request(
    body: ReportBulkGenerateRequest,
) -> ReportCreateRequest:
    return ReportCreateRequest(
        report_type=body.report_type,
        template_id=body.template_id,
        output_format=body.output_format,
        language=body.language,
    )
