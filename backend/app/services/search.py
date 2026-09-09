from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case_closure import CaseClosure, CaseDeliverable
from app.models.engagement import Engagement, EngagementScopeItem
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_evidence import InvestigationEvidence
from app.models.investigation_member import InvestigationMember
from app.models.ioc import IOC, IOCObservation
from app.models.notification import Notification
from app.models.report import Report
from app.models.saved_view import SavedView
from app.models.threat_workspace import ThreatCampaign, ThreatGroup, ThreatTechnique
from app.models.user import User
from app.schemas.search import (
    GlobalSearchResponse,
    GlobalSearchResult,
    GlobalSearchType,
    SavedViewCreate,
    SavedViewListResponse,
    SavedViewResponse,
    SavedViewType,
    SavedViewUpdate,
)
from app.services.audit import record_event

MAX_SEARCH_LIMIT = 50
SEARCHABLE_TYPES: tuple[GlobalSearchType, ...] = (
    "investigation",
    "engagement",
    "scope_item",
    "finding",
    "report",
    "deliverable",
    "notification",
    "closure",
    "evidence_summary",
    "ioc",
    "threat_object",
    "user",
)


class SavedViewNotFoundError(Exception):
    pass


class SavedViewConflictError(Exception):
    pass


class SavedViewForbiddenError(Exception):
    pass


async def global_search(
    db: AsyncSession,
    user: User,
    *,
    query: str,
    result_type: GlobalSearchType | None = None,
    limit: int = 25,
    offset: int = 0,
    include_archived: bool = False,
    investigation_id: uuid.UUID | None = None,
    engagement_id: uuid.UUID | None = None,
) -> GlobalSearchResponse:
    normalized = _normalize_query(query)
    effective_limit = min(max(limit, 1), MAX_SEARCH_LIMIT)
    types = (result_type,) if result_type else SEARCHABLE_TYPES
    accessible_ids = await _accessible_investigation_ids(db, user)
    results: list[GlobalSearchResult] = []

    for item_type in types:
        if item_type == "investigation":
            results.extend(
                await _search_investigations(
                    db,
                    user,
                    normalized,
                    accessible_ids,
                    include_archived=include_archived,
                    investigation_id=investigation_id,
                    limit=effective_limit,
                )
            )
        elif item_type == "engagement":
            results.extend(
                await _search_engagements(
                    db,
                    normalized,
                    include_archived=include_archived,
                    engagement_id=engagement_id,
                    limit=effective_limit,
                )
            )
        elif item_type == "scope_item":
            results.extend(
                await _search_scope_items(
                    db,
                    normalized,
                    engagement_id=engagement_id,
                    limit=effective_limit,
                )
            )
        elif item_type == "finding":
            results.extend(
                await _search_findings(
                    db,
                    normalized,
                    accessible_ids,
                    investigation_id=investigation_id,
                    limit=effective_limit,
                )
            )
        elif item_type == "report":
            results.extend(
                await _search_reports(
                    db,
                    normalized,
                    accessible_ids,
                    include_archived=include_archived,
                    investigation_id=investigation_id,
                    limit=effective_limit,
                )
            )
        elif item_type == "deliverable":
            results.extend(
                await _search_deliverables(
                    db,
                    normalized,
                    accessible_ids,
                    investigation_id=investigation_id,
                    limit=effective_limit,
                )
            )
        elif item_type == "notification":
            results.extend(
                await _search_notifications(
                    db,
                    user,
                    normalized,
                    investigation_id=investigation_id,
                    engagement_id=engagement_id,
                    limit=effective_limit,
                )
            )
        elif item_type == "closure":
            results.extend(
                await _search_closures(
                    db,
                    normalized,
                    accessible_ids,
                    investigation_id=investigation_id,
                    limit=effective_limit,
                )
            )
        elif item_type == "evidence_summary":
            results.extend(
                await _search_evidence(
                    db,
                    normalized,
                    accessible_ids,
                    investigation_id=investigation_id,
                    limit=effective_limit,
                )
            )
        elif item_type == "ioc":
            results.extend(
                await _search_iocs(
                    db,
                    normalized,
                    accessible_ids,
                    investigation_id=investigation_id,
                    limit=effective_limit,
                )
            )
        elif item_type == "threat_object":
            results.extend(await _search_threat_objects(db, normalized, effective_limit))
        elif item_type == "user" and user.role == "admin":
            results.extend(await _search_users(db, normalized, effective_limit))

    results.sort(key=lambda item: (item.score, _result_timestamp(item)), reverse=True)
    total = len(results)
    sliced = results[offset : offset + effective_limit]
    await record_event(
        db,
        action="search.performed",
        actor_id=user.id,
        resource_type="search",
        metadata={
            "query": normalized[:80],
            "result_count": total,
            "result_types": sorted({item.type for item in results}),
            "requested_type": result_type,
        },
    )
    return GlobalSearchResponse(
        query=normalized,
        total=total,
        limit=effective_limit,
        offset=offset,
        items=sliced,
        result_types=sorted({item.type for item in results}),
    )


async def list_saved_views(
    db: AsyncSession,
    user: User,
    *,
    view_type: str | None = None,
    pinned: bool | None = None,
) -> SavedViewListResponse:
    filters = [SavedView.user_id == user.id]
    if view_type:
        filters.append(SavedView.view_type == view_type)
    if pinned is not None:
        filters.append(SavedView.is_pinned.is_(pinned))
    result = await db.execute(
        select(SavedView)
        .where(*filters)
        .order_by(SavedView.is_pinned.desc(), SavedView.updated_at.desc())
    )
    items = list(result.scalars().all())
    return SavedViewListResponse(
        total=len(items),
        items=[_saved_view_response(item) for item in items],
    )


async def get_saved_view(
    db: AsyncSession,
    user: User,
    saved_view_id: uuid.UUID,
) -> SavedViewResponse:
    view = await _get_owned_saved_view(db, user, saved_view_id)
    return _saved_view_response(view)


async def create_saved_view(
    db: AsyncSession,
    user: User,
    body: SavedViewCreate,
) -> SavedViewResponse:
    await _ensure_unique_name(db, user.id, body.view_type, body.name)
    if body.is_default:
        await _unset_default_views(db, user.id, body.view_type)
    view = SavedView(
        user_id=user.id,
        name=body.name,
        description=body.description,
        view_type=body.view_type,
        route=_safe_route(body.route),
        filters=_safe_json(body.filters),
        sort=_safe_json(body.sort) if body.sort is not None else None,
        is_default=body.is_default,
        is_pinned=body.is_pinned,
    )
    db.add(view)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise SavedViewConflictError("A saved view with that name already exists.") from exc
    await record_event(
        db,
        action="saved_view.created",
        actor_id=user.id,
        resource_type="saved_view",
        resource_id=view.id,
        metadata={"view_type": view.view_type, "is_pinned": view.is_pinned},
    )
    await db.refresh(view)
    return _saved_view_response(view)


async def update_saved_view(
    db: AsyncSession,
    user: User,
    saved_view_id: uuid.UUID,
    body: SavedViewUpdate,
) -> SavedViewResponse:
    view = await _get_owned_saved_view(db, user, saved_view_id)
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != view.name:
        await _ensure_unique_name(
            db,
            user.id,
            str(updates.get("view_type") or view.view_type),
            str(updates["name"]),
            exclude_id=view.id,
        )
    if updates.get("is_default") is True:
        await _unset_default_views(
            db,
            user.id,
            str(updates.get("view_type") or view.view_type),
            exclude_id=view.id,
        )
    for field, value in updates.items():
        if field == "route" and value is not None:
            value = _safe_route(str(value))
        if field == "filters":
            value = _safe_json(value)
        if field == "sort":
            value = _safe_json(value) if value is not None else None
        setattr(view, field, value)
    db.add(view)
    await db.flush()
    await record_event(
        db,
        action="saved_view.updated",
        actor_id=user.id,
        resource_type="saved_view",
        resource_id=view.id,
        metadata={"view_type": view.view_type, "changed": sorted(updates)},
    )
    await db.refresh(view)
    return _saved_view_response(view)


async def delete_saved_view(
    db: AsyncSession,
    user: User,
    saved_view_id: uuid.UUID,
) -> None:
    view = await _get_owned_saved_view(db, user, saved_view_id)
    await db.delete(view)
    await record_event(
        db,
        action="saved_view.deleted",
        actor_id=user.id,
        resource_type="saved_view",
        resource_id=saved_view_id,
        metadata={"view_type": view.view_type},
    )
    await db.flush()


async def set_saved_view_pin(
    db: AsyncSession,
    user: User,
    saved_view_id: uuid.UUID,
    *,
    pinned: bool,
) -> SavedViewResponse:
    view = await _get_owned_saved_view(db, user, saved_view_id)
    view.is_pinned = pinned
    db.add(view)
    await db.flush()
    await record_event(
        db,
        action="saved_view.pinned" if pinned else "saved_view.unpinned",
        actor_id=user.id,
        resource_type="saved_view",
        resource_id=view.id,
        metadata={"view_type": view.view_type},
    )
    await db.refresh(view)
    return _saved_view_response(view)


async def set_saved_view_default(
    db: AsyncSession,
    user: User,
    saved_view_id: uuid.UUID,
) -> SavedViewResponse:
    view = await _get_owned_saved_view(db, user, saved_view_id)
    await _unset_default_views(db, user.id, view.view_type, exclude_id=view.id)
    view.is_default = True
    db.add(view)
    await db.flush()
    await record_event(
        db,
        action="saved_view.default_set",
        actor_id=user.id,
        resource_type="saved_view",
        resource_id=view.id,
        metadata={"view_type": view.view_type},
    )
    await db.refresh(view)
    return _saved_view_response(view)


async def _search_investigations(
    db: AsyncSession,
    user: User,
    query: str,
    accessible_ids: list[uuid.UUID],
    *,
    include_archived: bool,
    investigation_id: uuid.UUID | None,
    limit: int,
) -> list[GlobalSearchResult]:
    filters: list[Any] = []
    if user.role != "admin":
        if not accessible_ids:
            return []
        filters.append(Investigation.id.in_(accessible_ids))
    if not include_archived:
        filters.append(Investigation.status != "archived")
    if investigation_id:
        filters.append(Investigation.id == investigation_id)
    filters.extend(_text_filter(query, Investigation.title, Investigation.description))
    result = await db.execute(
        select(Investigation)
        .where(*filters)
        .order_by(Investigation.updated_at.desc())
        .limit(limit)
    )
    return [
        _result(
            item.id,
            "investigation",
            item.title,
            subtitle=item.status,
            snippet=item.description,
            status=item.status,
            route=f"/investigations/{item.id}",
            created_at=item.created_at,
            updated_at=item.updated_at,
            matched_fields=_matched_fields(query, title=item.title, description=item.description),
            metadata={"priority": item.priority, "stage": item.stage},
            query=query,
        )
        for item in result.scalars().all()
    ]


async def _search_engagements(
    db: AsyncSession,
    query: str,
    *,
    include_archived: bool,
    engagement_id: uuid.UUID | None,
    limit: int,
) -> list[GlobalSearchResult]:
    filters = []
    if not include_archived:
        filters.append(Engagement.status != "archived")
    if engagement_id:
        filters.append(Engagement.id == engagement_id)
    filters.extend(
        _text_filter(query, Engagement.title, Engagement.client_name, Engagement.description)
    )
    result = await db.execute(
        select(Engagement)
        .where(*filters)
        .order_by(Engagement.updated_at.desc())
        .limit(limit)
    )
    return [
        _result(
            item.id,
            "engagement",
            item.title,
            subtitle=item.client_name,
            snippet=item.description,
            status=item.status,
            route=f"/engagements?engagement={item.id}",
            created_at=item.created_at,
            updated_at=item.updated_at,
            matched_fields=_matched_fields(
                query,
                title=item.title,
                client_name=item.client_name,
                description=item.description,
            ),
            metadata={"authorization_status": item.authorization_status},
            query=query,
        )
        for item in result.scalars().all()
    ]


async def _search_scope_items(
    db: AsyncSession,
    query: str,
    *,
    engagement_id: uuid.UUID | None,
    limit: int,
) -> list[GlobalSearchResult]:
    filters = []
    if engagement_id:
        filters.append(EngagementScopeItem.engagement_id == engagement_id)
    filters.extend(
        _text_filter(
            query,
            EngagementScopeItem.value,
            EngagementScopeItem.description,
            EngagementScopeItem.scope_type,
        )
    )
    result = await db.execute(
        select(EngagementScopeItem, Engagement)
        .join(Engagement, Engagement.id == EngagementScopeItem.engagement_id)
        .where(*filters)
        .order_by(EngagementScopeItem.updated_at.desc())
        .limit(limit)
    )
    return [
        _result(
            item.id,
            "scope_item",
            item.value,
            subtitle=f"{item.scope_type} in {engagement.title}",
            snippet=item.description,
            status=item.status,
            route=f"/engagements?engagement={engagement.id}",
            created_at=item.created_at,
            updated_at=item.updated_at,
            matched_fields=_matched_fields(
                query,
                value=item.value,
                description=item.description,
                scope_type=item.scope_type,
            ),
            metadata={"engagement_id": str(engagement.id)},
            query=query,
        )
        for item, engagement in result.all()
    ]


async def _search_findings(
    db: AsyncSession,
    query: str,
    accessible_ids: list[uuid.UUID],
    *,
    investigation_id: uuid.UUID | None,
    limit: int,
) -> list[GlobalSearchResult]:
    ids = _scope_ids(accessible_ids, investigation_id)
    if ids is not None and not ids:
        return []
    filters = [Finding.investigation_id.in_(ids)] if ids is not None else []
    filters.extend(_text_filter(query, Finding.title, Finding.description, Finding.source))
    result = await db.execute(
        select(Finding, Investigation)
        .join(Investigation, Investigation.id == Finding.investigation_id)
        .where(*filters)
        .order_by(Finding.updated_at.desc())
        .limit(limit)
    )
    return [
        _result(
            finding.id,
            "finding",
            finding.title,
            subtitle=investigation.title,
            snippet=finding.description,
            status=finding.status,
            severity=finding.severity,
            route=f"/investigations/{finding.investigation_id}/findings",
            created_at=finding.created_at,
            updated_at=finding.updated_at,
            matched_fields=_matched_fields(
                query,
                title=finding.title,
                description=finding.description,
                source=finding.source,
            ),
            metadata={"investigation_id": str(finding.investigation_id)},
            query=query,
        )
        for finding, investigation in result.all()
    ]


async def _search_reports(
    db: AsyncSession,
    query: str,
    accessible_ids: list[uuid.UUID],
    *,
    include_archived: bool,
    investigation_id: uuid.UUID | None,
    limit: int,
) -> list[GlobalSearchResult]:
    ids = _scope_ids(accessible_ids, investigation_id)
    if ids is not None and not ids:
        return []
    filters: list[Any] = [Report.investigation_id.in_(ids)] if ids is not None else []
    if not include_archived:
        filters.append(Report.status != "archived")
    filters.extend(_text_filter(query, Report.title, Report.report_type, Report.status))
    result = await db.execute(
        select(Report, Investigation)
        .join(Investigation, Investigation.id == Report.investigation_id)
        .where(*filters)
        .order_by(Report.created_at.desc())
        .limit(limit)
    )
    return [
        _result(
            report.id,
            "report",
            report.title or f"{report.report_type} report",
            subtitle=investigation.title,
            snippet=report.progress_label or report.failure_reason,
            status=report.status,
            route=f"/investigations/{report.investigation_id}/reports",
            created_at=report.created_at,
            updated_at=report.generated_at or report.created_at,
            matched_fields=_matched_fields(
                query,
                title=report.title,
                report_type=report.report_type,
                status=report.status,
            ),
            metadata={
                "report_type": report.report_type,
                "report_format": report.report_format,
            },
            query=query,
        )
        for report, investigation in result.all()
    ]


async def _search_deliverables(
    db: AsyncSession,
    query: str,
    accessible_ids: list[uuid.UUID],
    *,
    investigation_id: uuid.UUID | None,
    limit: int,
) -> list[GlobalSearchResult]:
    ids = _scope_ids(accessible_ids, investigation_id)
    if ids is not None and not ids:
        return []
    filters = [CaseDeliverable.investigation_id.in_(ids)] if ids is not None else []
    filters.extend(
        _text_filter(
            query,
            CaseDeliverable.title,
            CaseDeliverable.deliverable_type,
            CaseDeliverable.status,
        )
    )
    result = await db.execute(
        select(CaseDeliverable, Investigation)
        .join(Investigation, Investigation.id == CaseDeliverable.investigation_id)
        .where(*filters)
        .order_by(CaseDeliverable.updated_at.desc())
        .limit(limit)
    )
    return [
        _result(
            deliverable.id,
            "deliverable",
            deliverable.title,
            subtitle=investigation.title,
            snippet=deliverable.deliverable_type,
            status=deliverable.status,
            route=f"/investigations/{deliverable.investigation_id}/closure",
            created_at=deliverable.created_at,
            updated_at=deliverable.updated_at,
            matched_fields=_matched_fields(
                query,
                title=deliverable.title,
                deliverable_type=deliverable.deliverable_type,
                status=deliverable.status,
            ),
            metadata={"export_format": deliverable.export_format},
            query=query,
        )
        for deliverable, investigation in result.all()
    ]


async def _search_notifications(
    db: AsyncSession,
    user: User,
    query: str,
    *,
    investigation_id: uuid.UUID | None,
    engagement_id: uuid.UUID | None,
    limit: int,
) -> list[GlobalSearchResult]:
    filters = [Notification.user_id == user.id]
    if investigation_id:
        filters.append(Notification.investigation_id == investigation_id)
    if engagement_id:
        filters.append(Notification.engagement_id == engagement_id)
    filters.extend(
        _text_filter(
            query,
            Notification.title,
            Notification.message,
            Notification.notification_type,
        )
    )
    result = await db.execute(
        select(Notification)
        .where(*filters)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return [
        _result(
            item.id,
            "notification",
            item.title,
            subtitle=item.notification_type,
            snippet=item.message,
            status=item.status,
            severity=item.severity,
            route=item.action_url or "/notifications",
            created_at=item.created_at,
            updated_at=item.updated_at,
            matched_fields=_matched_fields(
                query,
                title=item.title,
                message=item.message,
                notification_type=item.notification_type,
            ),
            metadata={"entity_type": item.entity_type},
            query=query,
        )
        for item in result.scalars().all()
    ]


async def _search_closures(
    db: AsyncSession,
    query: str,
    accessible_ids: list[uuid.UUID],
    *,
    investigation_id: uuid.UUID | None,
    limit: int,
) -> list[GlobalSearchResult]:
    ids = _scope_ids(accessible_ids, investigation_id)
    if ids is not None and not ids:
        return []
    filters = [CaseClosure.investigation_id.in_(ids)] if ids is not None else []
    filters.extend(
        _text_filter(
            query,
            CaseClosure.closure_summary,
            CaseClosure.status,
            CaseClosure.final_risk_rating,
        )
    )
    result = await db.execute(
        select(CaseClosure, Investigation)
        .join(Investigation, Investigation.id == CaseClosure.investigation_id)
        .where(*filters)
        .order_by(CaseClosure.updated_at.desc())
        .limit(limit)
    )
    return [
        _result(
            closure.id,
            "closure",
            f"Closure: {investigation.title}",
            subtitle=closure.final_risk_rating,
            snippet=closure.closure_summary,
            status=closure.status,
            route=f"/investigations/{closure.investigation_id}/closure",
            created_at=closure.created_at,
            updated_at=closure.updated_at,
            matched_fields=_matched_fields(
                query,
                closure_summary=closure.closure_summary,
                status=closure.status,
                final_risk_rating=closure.final_risk_rating,
            ),
            metadata={"investigation_id": str(closure.investigation_id)},
            query=query,
        )
        for closure, investigation in result.all()
    ]


async def _search_evidence(
    db: AsyncSession,
    query: str,
    accessible_ids: list[uuid.UUID],
    *,
    investigation_id: uuid.UUID | None,
    limit: int,
) -> list[GlobalSearchResult]:
    ids = _scope_ids(accessible_ids, investigation_id)
    if ids is not None and not ids:
        return []
    filters = [InvestigationEvidence.investigation_id.in_(ids)] if ids is not None else []
    filters.extend(
        _text_filter(
            query,
            InvestigationEvidence.title,
            InvestigationEvidence.description,
            InvestigationEvidence.evidence_type,
        )
    )
    result = await db.execute(
        select(InvestigationEvidence, Investigation)
        .join(Investigation, Investigation.id == InvestigationEvidence.investigation_id)
        .where(*filters)
        .order_by(InvestigationEvidence.created_at.desc())
        .limit(limit)
    )
    return [
        _result(
            evidence.id,
            "evidence_summary",
            evidence.title,
            subtitle=investigation.title,
            snippet=evidence.description,
            status=evidence.evidence_type,
            route=f"/investigations/{evidence.investigation_id}",
            created_at=evidence.created_at,
            updated_at=evidence.created_at,
            matched_fields=_matched_fields(
                query,
                title=evidence.title,
                description=evidence.description,
                evidence_type=evidence.evidence_type,
            ),
            metadata={"investigation_id": str(evidence.investigation_id)},
            query=query,
        )
        for evidence, investigation in result.all()
    ]


async def _search_iocs(
    db: AsyncSession,
    query: str,
    accessible_ids: list[uuid.UUID],
    *,
    investigation_id: uuid.UUID | None,
    limit: int,
) -> list[GlobalSearchResult]:
    ids = _scope_ids(accessible_ids, investigation_id)
    if ids is not None and not ids:
        return []
    filters = []
    if ids is not None:
        filters.append(IOCObservation.investigation_id.in_(ids))
    filters.extend(_text_filter(query, IOC.value, IOC.normalized_value, IOC.ioc_type))
    stmt = (
        select(IOC)
        .outerjoin(IOCObservation, IOCObservation.ioc_id == IOC.id)
        .where(*filters)
        .group_by(IOC.id)
        .order_by(IOC.last_seen.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        _result(
            item.id,
            "ioc",
            item.value,
            subtitle=item.ioc_type,
            snippet=item.confidence_reason,
            status=item.confidence,
            route="/threat-intelligence",
            created_at=item.created_at,
            updated_at=item.updated_at,
            matched_fields=_matched_fields(
                query,
                value=item.value,
                normalized_value=item.normalized_value,
                ioc_type=item.ioc_type,
            ),
            metadata={"source": item.source},
            query=query,
        )
        for item in result.scalars().all()
    ]


async def _search_threat_objects(
    db: AsyncSession,
    query: str,
    limit: int,
) -> list[GlobalSearchResult]:
    results: list[GlobalSearchResult] = []
    campaign_filters = _text_filter(query, ThreatCampaign.name, ThreatCampaign.description)
    campaigns = await db.execute(
        select(ThreatCampaign)
        .where(*campaign_filters)
        .order_by(ThreatCampaign.updated_at.desc())
        .limit(limit)
    )
    for campaign in campaigns.scalars().all():
        results.append(
            _result(
                campaign.id,
                "threat_object",
                campaign.name,
                subtitle="campaign",
                snippet=campaign.description,
                status=campaign.status,
                route="/threat-intelligence",
                created_at=campaign.created_at,
                updated_at=campaign.updated_at,
                matched_fields=_matched_fields(
                    query,
                    name=campaign.name,
                    description=campaign.description,
                ),
                metadata={"object_type": "campaign", "confidence": campaign.confidence},
                query=query,
            )
        )
    group_filters = _text_filter(query, ThreatGroup.name, ThreatGroup.description)
    groups = await db.execute(
        select(ThreatGroup)
        .where(*group_filters)
        .order_by(ThreatGroup.updated_at.desc())
        .limit(limit)
    )
    for group in groups.scalars().all():
        results.append(
            _result(
                group.id,
                "threat_object",
                group.name,
                subtitle="threat group",
                snippet=group.description,
                status=group.confidence,
                route="/threat-intelligence",
                created_at=group.created_at,
                updated_at=group.updated_at,
                matched_fields=_matched_fields(
                    query,
                    name=group.name,
                    description=group.description,
                ),
                metadata={"object_type": "group"},
                query=query,
            )
        )
    technique_filters = _text_filter(
        query,
        ThreatTechnique.technique_id,
        ThreatTechnique.name,
        ThreatTechnique.tactic,
    )
    techniques = await db.execute(
        select(ThreatTechnique)
        .where(*technique_filters)
        .order_by(ThreatTechnique.updated_at.desc())
        .limit(limit)
    )
    for technique in techniques.scalars().all():
        results.append(
            _result(
                technique.id,
                "threat_object",
                f"{technique.technique_id} {technique.name}",
                subtitle=technique.tactic or "ATT&CK technique",
                snippet=technique.procedure,
                status=None,
                route="/threat-intelligence",
                created_at=technique.created_at,
                updated_at=technique.updated_at,
                matched_fields=_matched_fields(
                    query,
                    technique_id=technique.technique_id,
                    name=technique.name,
                    tactic=technique.tactic,
                ),
                metadata={"object_type": "technique"},
                query=query,
            )
        )
    return results[:limit]


async def _search_users(
    db: AsyncSession,
    query: str,
    limit: int,
) -> list[GlobalSearchResult]:
    filters = _text_filter(query, User.username, User.email, User.full_name)
    result = await db.execute(
        select(User).where(*filters).order_by(User.created_at.desc()).limit(limit)
    )
    return [
        _result(
            item.id,
            "user",
            item.username,
            subtitle=item.email,
            snippet=item.full_name,
            status=item.account_status,
            route=f"/admin/users?search={item.username}",
            created_at=item.created_at,
            updated_at=item.updated_at,
            matched_fields=_matched_fields(
                query,
                username=item.username,
                email=item.email,
                full_name=item.full_name,
            ),
            metadata={"role": item.role, "is_active": item.is_active},
            query=query,
        )
        for item in result.scalars().all()
    ]


async def _accessible_investigation_ids(db: AsyncSession, user: User) -> list[uuid.UUID]:
    if user.role == "admin":
        result = await db.execute(select(Investigation.id))
        return list(result.scalars().all())
    result = await db.execute(
        select(Investigation.id)
        .outerjoin(
            InvestigationMember,
            InvestigationMember.investigation_id == Investigation.id,
        )
        .where(
            or_(
                Investigation.owner_id == user.id,
                Investigation.reviewer_id == user.id,
                InvestigationMember.user_id == user.id,
            )
        )
        .group_by(Investigation.id)
    )
    return list(result.scalars().all())


def _scope_ids(
    accessible_ids: list[uuid.UUID],
    investigation_id: uuid.UUID | None,
) -> list[uuid.UUID] | None:
    if investigation_id is None:
        return accessible_ids
    return [investigation_id] if investigation_id in set(accessible_ids) else []


def _text_filter(query: str, *columns: Any) -> list[Any]:
    if not query:
        return []
    pattern = f"%{_escape_like(query)}%"
    return [or_(*[column.ilike(pattern, escape="\\") for column in columns])]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _matched_fields(query: str, **fields: object) -> list[str]:
    if not query:
        return []
    needle = query.lower()
    return [
        name
        for name, value in fields.items()
        if isinstance(value, str) and needle in value.lower()
    ]


def _result(
    item_id: uuid.UUID,
    item_type: GlobalSearchType,
    title: str,
    *,
    subtitle: str | None,
    snippet: str | None,
    status: str | None,
    route: str,
    created_at: datetime | None,
    updated_at: datetime | None,
    matched_fields: list[str],
    metadata: dict[str, Any],
    query: str,
    severity: str | None = None,
) -> GlobalSearchResult:
    clean_title = _clean_text(title, 180) or "Untitled result"
    return GlobalSearchResult(
        id=str(item_id),
        type=item_type,
        title=clean_title,
        subtitle=_clean_text(subtitle, 180),
        snippet=_snippet(snippet, query),
        status=_clean_text(status, 80),
        severity=_clean_text(severity, 40),
        route=_safe_route(route),
        created_at=created_at,
        updated_at=updated_at,
        matched_fields=matched_fields,
        metadata=_safe_json(metadata),
        score=_score(clean_title, query, matched_fields, updated_at or created_at),
    )


def _score(
    title: str,
    query: str,
    matched_fields: list[str],
    timestamp: datetime | None,
) -> int:
    if not query:
        return 10 + (1 if timestamp else 0)
    title_lower = title.lower()
    query_lower = query.lower()
    score = 10 + len(matched_fields) * 5
    if title_lower == query_lower:
        score += 100
    elif title_lower.startswith(query_lower):
        score += 60
    elif query_lower in title_lower:
        score += 35
    return score


def _result_timestamp(item: GlobalSearchResult) -> float:
    value = item.updated_at or item.created_at
    return value.timestamp() if value else 0.0


def _snippet(value: str | None, query: str) -> str | None:
    clean = _clean_text(value, 500)
    if clean is None:
        return None
    if not query:
        return clean[:180]
    index = clean.lower().find(query.lower())
    if index < 0:
        return clean[:180]
    start = max(index - 60, 0)
    end = min(index + len(query) + 120, len(clean))
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean) else ""
    return f"{prefix}{clean[start:end]}{suffix}"


def _clean_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    clean = " ".join(value.strip().split())
    return clean[:limit] if clean else None


def _normalize_query(value: str) -> str:
    return " ".join(value.strip().split())[:120]


def _safe_route(route: str) -> str:
    clean = route.strip()
    if not clean.startswith("/") or clean.startswith("//"):
        return "/"
    if any(marker in clean.lower() for marker in ("javascript:", "data:", "://")):
        return "/"
    return clean[:500]


def _safe_json(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    blocked = {
        "password",
        "hashed_password",
        "token",
        "api_key",
        "secret",
        "authorization",
        "database_url",
        "invite_code",
        "file_path",
    }
    clean: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        if key_text.lower() in blocked:
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            clean[key_text] = item
        elif isinstance(item, list):
            clean[key_text] = [
                entry
                for entry in item[:25]
                if isinstance(entry, (str, int, float, bool)) or entry is None
            ]
        elif isinstance(item, dict):
            clean[key_text] = {
                str(child_key): child_value
                for child_key, child_value in list(item.items())[:25]
                if isinstance(child_value, (str, int, float, bool))
                or child_value is None
            }
    return clean


async def _get_owned_saved_view(
    db: AsyncSession,
    user: User,
    saved_view_id: uuid.UUID,
) -> SavedView:
    view = await db.get(SavedView, saved_view_id)
    if view is None:
        raise SavedViewNotFoundError("Saved view not found")
    if view.user_id != user.id:
        raise SavedViewNotFoundError("Saved view not found")
    return view


async def _ensure_unique_name(
    db: AsyncSession,
    user_id: uuid.UUID,
    view_type: str,
    name: str,
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    filters = [
        SavedView.user_id == user_id,
        SavedView.view_type == view_type,
        func.lower(SavedView.name) == name.lower(),
    ]
    if exclude_id:
        filters.append(SavedView.id != exclude_id)
    result = await db.execute(select(SavedView.id).where(*filters).limit(1))
    if result.scalar_one_or_none() is not None:
        raise SavedViewConflictError("A saved view with that name already exists.")


async def _unset_default_views(
    db: AsyncSession,
    user_id: uuid.UUID,
    view_type: str,
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    filters = [
        SavedView.user_id == user_id,
        SavedView.view_type == view_type,
        SavedView.is_default.is_(True),
    ]
    if exclude_id:
        filters.append(SavedView.id != exclude_id)
    result = await db.execute(select(SavedView).where(*filters))
    for view in result.scalars().all():
        view.is_default = False
        db.add(view)


def _saved_view_response(view: SavedView) -> SavedViewResponse:
    return SavedViewResponse(
        id=view.id,
        user_id=view.user_id,
        name=view.name,
        description=view.description,
        view_type=cast(SavedViewType, view.view_type),
        route=view.route,
        filters=_safe_json(view.filters),
        sort=_safe_json(view.sort) if view.sort else None,
        is_default=view.is_default,
        is_pinned=view.is_pinned,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )
