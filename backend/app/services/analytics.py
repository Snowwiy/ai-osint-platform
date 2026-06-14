from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_analysis import AiAnalysis
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.investigation_task import InvestigationTask
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.report import Report
from app.models.target import Target
from app.models.threat_finding import ThreatFinding
from app.models.user import User
from app.schemas.analytics import (
    AiAnalysisAnalyticsSummary,
    CorrelationAnalyticsSummary,
    CountItem,
    DashboardAnalyticsResponse,
    DashboardMetricsResponse,
    FindingAnalyticsItem,
    FindingsAnalyticsSummary,
    InvestigationAnalyticsItem,
    InvestigationAnalyticsResponse,
    InvestigationDashboardSummary,
    InvestigationMetricsSummary,
    LatestActivityItem,
    OpenHighRiskItem,
    ReconAnalyticsSummary,
    ReportAnalyticsItem,
    ReportAnalyticsSummary,
    RiskLevel,
    RiskMetricsSummary,
    RiskSummary,
    TargetAnalyticsSummary,
    TimelineAnalyticsSummary,
    AnalystMetricsSummary,
)
from app.schemas.finding import FindingSeverity, FindingStatus
from app.schemas.case_management import InvestigationWorkflowStatus
from app.schemas.timeline import TimelineEvent
from app.services.correlation.service import get_investigation_correlations
from app.services.investigation import get_investigation
from app.services.timeline.service import collect_timeline_events

_SEVERITIES: tuple[FindingSeverity, ...] = (
    "critical",
    "high",
    "medium",
    "low",
    "info",
)
_STATUSES: tuple[FindingStatus, ...] = (
    "new",
    "under_review",
    "validated",
    "accepted_risk",
    "mitigated",
    "false_positive",
    "archived",
    "open",
    "resolved",
)
_INVESTIGATION_STATUSES: tuple[InvestigationWorkflowStatus, ...] = (
    "draft",
    "active",
    "triage",
    "monitoring",
    "remediation",
    "validated",
    "archived",
    "review",
    "remediated",
)
_SEVERITY_RANK: dict[FindingSeverity, int] = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}


@dataclass(frozen=True)
class InvestigationAnalyticsDataset:
    targets: list[Target]
    entities: list[ReconEntity]
    relationships: list[ReconRelationship]
    findings: list[Finding]
    threat_findings: list[ThreatFinding]
    reports: list[Report]
    ai_analyses: list[AiAnalysis]


async def get_investigation_analytics(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> InvestigationAnalyticsResponse:
    investigation = await get_investigation(db, user, investigation_id)
    dataset = await _load_investigation_dataset(db, investigation_id)
    timeline_events = await collect_timeline_events(db, investigation)
    correlations = await get_investigation_correlations(db, user, investigation_id)

    return InvestigationAnalyticsResponse(
        investigation_id=investigation_id,
        generated_at=_now(),
        risk_summary=_build_risk_summary(dataset.findings, dataset.threat_findings),
        findings_summary=_build_findings_summary(dataset.findings),
        recon_summary=_build_recon_summary(dataset.entities, dataset.relationships),
        target_summary=_build_target_summary(dataset.targets),
        correlation_summary=CorrelationAnalyticsSummary(
            total_nodes=correlations.total_nodes,
            total_edges=correlations.total_edges,
            by_confidence=_count_strings(edge.confidence for edge in correlations.edges),
        ),
        report_summary=_build_report_summary(dataset.reports),
        ai_analysis_summary=_build_ai_summary(dataset.ai_analyses),
        timeline_summary=_build_timeline_summary(timeline_events),
        top_assets=_top_assets(dataset.findings, dataset.entities),
        top_technologies=_top_technologies(dataset.entities),
        latest_activity=_latest_activity(timeline_events),
    )


async def get_dashboard_analytics(
    db: AsyncSession,
    user: User,
) -> DashboardAnalyticsResponse:
    investigations = await _accessible_investigations(db, user)
    investigation_ids = [item.id for item in investigations]
    targets = await _load_targets(db, investigation_ids)
    entities = await _load_entities(db, investigation_ids)
    relationships = await _load_relationships(db, investigation_ids)
    findings = await _load_findings(db, investigation_ids)
    reports = await _load_reports(db, investigation_ids)
    ai_analyses = await _load_ai_analyses(db, investigation_ids)
    timeline_events = await _dashboard_timeline_events(db, investigations)
    investigation_title_by_id = {item.id: item.title for item in investigations}

    latest_reports = _latest_reports(reports)
    return DashboardAnalyticsResponse(
        generated_at=_now(),
        investigation_summary=_build_investigation_summary(investigations),
        target_summary=_build_target_summary(targets),
        recon_summary=_build_recon_summary(entities, relationships),
        findings_summary=_build_findings_summary(findings),
        report_summary=_build_report_summary(reports),
        ai_analysis_summary=_build_ai_summary(ai_analyses),
        timeline_summary=_build_timeline_summary(timeline_events),
        latest_investigations=[
            _investigation_item(item)
            for item in sorted(
                investigations,
                key=lambda investigation: investigation.updated_at,
                reverse=True,
            )[:5]
        ],
        latest_reports=latest_reports,
        recent_activity=_latest_activity(timeline_events),
        open_high_risk_items=_open_high_risk_items(findings, investigation_title_by_id),
    )


async def get_dashboard_metrics(
    db: AsyncSession,
    user: User,
) -> DashboardMetricsResponse:
    investigations = await _accessible_investigations(db, user)
    investigation_ids = [item.id for item in investigations]
    findings = await _load_findings(db, investigation_ids)
    tasks = await _load_tasks(db, investigation_ids)
    now = _now()
    assigned_investigations = [
        item
        for item in investigations
        if item.owner_id == user.id or item.reviewer_id == user.id
    ]
    assigned_findings = [
        finding
        for finding in findings
        if finding.assigned_to == user.id or finding.reviewed_by == user.id
    ]
    open_tasks = [task for task in tasks if task.status not in _CLOSED_TASK_STATUSES]
    overdue_tasks = [
        task
        for task in open_tasks
        if task.due_date is not None and task.due_date < now
    ]
    unresolved_findings = [
        finding for finding in findings if _finding_status(finding.status) in _OPEN_STATUSES
    ]
    completed_remediations = [
        task for task in tasks if task.status == "completed" and task.finding_id is not None
    ]
    health_score = _health_score(findings, open_tasks, overdue_tasks)
    return DashboardMetricsResponse(
        generated_at=now,
        investigation_metrics=InvestigationMetricsSummary(
            findings_count=len(findings),
            validated_findings=sum(
                1 for finding in findings if finding.status == "validated"
            ),
            open_tasks=len(open_tasks),
            overdue_tasks=len(overdue_tasks),
            average_confidence=_average_confidence(findings),
            health_score=health_score,
            urgent_investigations=sum(
                1
                for investigation in investigations
                if investigation.priority == "urgent"
                and investigation.status != "archived"
            ),
            overdue_investigations=sum(
                1
                for investigation in investigations
                if investigation.due_date is not None
                and investigation.due_date < now.date()
                and investigation.status != "archived"
            ),
        ),
        analyst_metrics=AnalystMetricsSummary(
            assigned_investigations=len(assigned_investigations),
            assigned_findings=len(assigned_findings),
            pending_reviews=sum(
                1 for finding in findings if finding.status == "under_review"
            ),
            completed_remediations=len(completed_remediations),
        ),
        risk_metrics=RiskMetricsSummary(
            severity_distribution={
                severity: sum(
                    1
                    for finding in findings
                    if _finding_severity(finding.severity) == severity
                )
                for severity in _SEVERITIES
            },
            confidence_average=_average_confidence(findings),
            unresolved_findings=len(unresolved_findings),
        ),
    )


async def _load_investigation_dataset(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> InvestigationAnalyticsDataset:
    investigation_ids = [investigation_id]
    return InvestigationAnalyticsDataset(
        targets=await _load_targets(db, investigation_ids),
        entities=await _load_entities(db, investigation_ids),
        relationships=await _load_relationships(db, investigation_ids),
        findings=await _load_findings(db, investigation_ids),
        threat_findings=await _load_threat_findings(db, investigation_ids),
        reports=await _load_reports(db, investigation_ids),
        ai_analyses=await _load_ai_analyses(db, investigation_ids),
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
                Investigation.id == InvestigationMember.investigation_id,
            )
            .where(InvestigationMember.user_id == user.id)
        )
    return list(result.scalars().all())


async def _load_targets(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[Target]:
    if not investigation_ids:
        return []
    result = await db.execute(
        select(Target).where(Target.investigation_id.in_(investigation_ids))
    )
    return list(result.scalars().all())


async def _load_entities(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[ReconEntity]:
    if not investigation_ids:
        return []
    result = await db.execute(
        select(ReconEntity).where(ReconEntity.investigation_id.in_(investigation_ids))
    )
    return list(result.scalars().all())


async def _load_relationships(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[ReconRelationship]:
    if not investigation_ids:
        return []
    result = await db.execute(
        select(ReconRelationship).where(
            ReconRelationship.investigation_id.in_(investigation_ids)
        )
    )
    return list(result.scalars().all())


async def _load_findings(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[Finding]:
    if not investigation_ids:
        return []
    result = await db.execute(
        select(Finding).where(Finding.investigation_id.in_(investigation_ids))
    )
    return list(result.scalars().all())


async def _load_tasks(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[InvestigationTask]:
    if not investigation_ids:
        return []
    result = await db.execute(
        select(InvestigationTask).where(
            InvestigationTask.investigation_id.in_(investigation_ids)
        )
    )
    return list(result.scalars().all())


async def _load_threat_findings(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[ThreatFinding]:
    if not investigation_ids:
        return []
    result = await db.execute(
        select(ThreatFinding).where(
            ThreatFinding.investigation_id.in_(investigation_ids)
        )
    )
    return list(result.scalars().all())


async def _load_reports(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[Report]:
    if not investigation_ids:
        return []
    result = await db.execute(
        select(Report).where(Report.investigation_id.in_(investigation_ids))
    )
    return list(result.scalars().all())


async def _load_ai_analyses(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[AiAnalysis]:
    if not investigation_ids:
        return []
    result = await db.execute(
        select(AiAnalysis)
        .join(Target, AiAnalysis.target_id == Target.id)
        .where(Target.investigation_id.in_(investigation_ids))
    )
    return list(result.scalars().all())


async def _dashboard_timeline_events(
    db: AsyncSession,
    investigations: list[Investigation],
) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for investigation in investigations:
        events.extend(await collect_timeline_events(db, investigation))
    return events


def _build_investigation_summary(
    investigations: list[Investigation],
) -> InvestigationDashboardSummary:
    counts: dict[InvestigationWorkflowStatus, int] = {
        status: 0 for status in _INVESTIGATION_STATUSES
    }
    for investigation in investigations:
        status = _investigation_status(investigation.status)
        counts[status] += 1
    return InvestigationDashboardSummary(
        total=len(investigations),
        active=counts["active"] + counts["triage"] + counts["monitoring"],
        closed=counts["validated"] + counts["archived"] + counts["remediated"],
        by_status=counts,
    )


def _build_risk_summary(
    findings: list[Finding],
    threat_findings: list[ThreatFinding],
) -> RiskSummary:
    finding_scores = [finding.risk_score for finding in findings]
    threat_scores = [finding.risk_score for finding in threat_findings]
    risk_score = max(finding_scores + threat_scores, default=0)
    highest = _highest_severity_finding(findings)
    return RiskSummary(
        risk_score=risk_score,
        risk_level=_risk_level(risk_score),
        highest_severity=_finding_severity(highest.severity) if highest else None,
        highest_severity_finding=_finding_item(highest) if highest else None,
        high_or_critical_findings=sum(
            1
            for finding in findings
            if _finding_severity(finding.severity) in {"high", "critical"}
        ),
        average_finding_confidence=_average_confidence(findings),
    )


def _build_findings_summary(findings: list[Finding]) -> FindingsAnalyticsSummary:
    severity_counts: dict[FindingSeverity, int] = {key: 0 for key in _SEVERITIES}
    status_counts: dict[FindingStatus, int] = {key: 0 for key in _STATUSES}
    for finding in findings:
        severity_counts[_finding_severity(finding.severity)] += 1
        status_counts[_finding_status(finding.status)] += 1
    highest = _highest_severity_finding(findings)
    return FindingsAnalyticsSummary(
        total=len(findings),
        by_severity=severity_counts,
        by_status=status_counts,
        average_confidence=_average_confidence(findings),
        highest_severity_finding=_finding_item(highest) if highest else None,
    )


def _build_recon_summary(
    entities: list[ReconEntity],
    relationships: list[ReconRelationship],
) -> ReconAnalyticsSummary:
    return ReconAnalyticsSummary(
        total_entities=len(entities),
        entity_counts=_count_strings(entity.entity_type for entity in entities),
        relationship_count=len(relationships),
        top_external_dependencies=_top_external_dependencies(entities),
        top_technologies=_top_technologies(entities),
    )


def _build_target_summary(targets: list[Target]) -> TargetAnalyticsSummary:
    return TargetAnalyticsSummary(
        total=len(targets),
        by_type=_count_strings(target.target_type for target in targets),
    )


def _build_report_summary(reports: list[Report]) -> ReportAnalyticsSummary:
    latest_reports = _latest_reports(reports)
    return ReportAnalyticsSummary(
        total=len(reports),
        by_type=_count_strings(report.report_type for report in reports),
        by_status=_count_strings(report.status for report in reports),
        ready=sum(1 for report in reports if report.status == "ready"),
        latest_reports=latest_reports,
    )


def _build_ai_summary(analyses: list[AiAnalysis]) -> AiAnalysisAnalyticsSummary:
    latest = max((analysis.created_at for analysis in analyses), default=None)
    return AiAnalysisAnalyticsSummary(
        total=len(analyses),
        available=bool(analyses),
        latest_at=latest,
        by_risk=_count_strings(analysis.risk_assessment for analysis in analyses),
    )


def _build_timeline_summary(
    events: Sequence[TimelineEvent | LatestActivityItem],
) -> TimelineAnalyticsSummary:
    return TimelineAnalyticsSummary(
        total=len(events),
        by_event_type=_count_strings(_timeline_event_type(item) for item in events),
        by_source=_count_strings(item.source for item in events),
    )


def _latest_activity(
    events: Sequence[TimelineEvent | LatestActivityItem],
    *,
    limit: int = 10,
) -> list[LatestActivityItem]:
    activity = [_activity_item(event) for event in events]
    return sorted(
        activity,
        key=lambda item: item.timestamp,
        reverse=True,
    )[:limit]


def _activity_item(event: TimelineEvent | LatestActivityItem) -> LatestActivityItem:
    if isinstance(event, LatestActivityItem):
        return event
    return LatestActivityItem(
        id=event.id,
        timestamp=event.timestamp,
        source=event.source,
        title=event.title,
        summary=event.summary,
        severity=event.severity,
    )


def _top_assets(
    findings: list[Finding],
    entities: list[ReconEntity],
) -> list[CountItem]:
    counter: Counter[str] = Counter()
    for finding in findings:
        affected = finding.normalized_data.get("affected_targets")
        if isinstance(affected, list):
            for value in affected:
                if isinstance(value, str) and value.strip():
                    counter[value.strip()] += 1
    if not counter:
        for entity in entities:
            if entity.entity_type in {"Domain", "Subdomain", "IPAddress", "Service"}:
                counter[entity.value] += 1
    return _top_count_items(counter)


def _top_technologies(entities: list[ReconEntity]) -> list[CountItem]:
    counter: Counter[str] = Counter()
    for entity in entities:
        for value in _technologies_from_entity(entity):
            counter[value] += 1
    return _top_count_items(counter)


def _top_external_dependencies(entities: list[ReconEntity]) -> list[CountItem]:
    counter: Counter[str] = Counter()
    for entity in entities:
        if entity.entity_type == "Organization":
            counter[entity.display_name or entity.value] += 1
        elif entity.entity_type == "ASN":
            counter[_first_string(entity.properties, ("organization", "provider"))] += 1
        elif entity.entity_type == "Certificate":
            issuer = _first_string(entity.properties, ("issuer", "issuer_common_name"))
            counter[issuer] += 1
        elif entity.entity_type == "IPAddress":
            provider = _first_string(entity.properties, ("provider", "organization"))
            counter[provider] += 1
    counter.pop("unknown", None)
    return _top_count_items(counter)


def _open_high_risk_items(
    findings: list[Finding],
    investigation_title_by_id: dict[uuid.UUID, str],
) -> list[OpenHighRiskItem]:
    high_risk = [
        finding
        for finding in findings
        if _finding_severity(finding.severity) in {"high", "critical"}
        and _finding_status(finding.status) in _OPEN_STATUSES
    ]
    sorted_findings = sorted(
        high_risk,
        key=lambda item: (
            _SEVERITY_RANK[_finding_severity(item.severity)],
            item.risk_score,
            item.created_at,
        ),
        reverse=True,
    )
    return [
        OpenHighRiskItem(
            finding_id=finding.id,
            investigation_id=finding.investigation_id,
            investigation_title=investigation_title_by_id.get(
                finding.investigation_id,
                "Investigation",
            ),
            title=finding.title,
            severity=_finding_severity(finding.severity),
            risk_score=finding.risk_score,
            created_at=finding.created_at,
        )
        for finding in sorted_findings[:10]
    ]


def _highest_severity_finding(findings: list[Finding]) -> Finding | None:
    if not findings:
        return None
    return max(
        findings,
        key=lambda finding: (
            _SEVERITY_RANK[_finding_severity(finding.severity)],
            finding.risk_score,
            finding.created_at,
        ),
    )


def _finding_item(finding: Finding) -> FindingAnalyticsItem:
    return FindingAnalyticsItem(
        id=finding.id,
        investigation_id=finding.investigation_id,
        title=finding.title,
        severity=_finding_severity(finding.severity),
        status=_finding_status(finding.status),
        source=finding.source,
        risk_score=finding.risk_score,
        confidence_score=finding.confidence_score,
        created_at=finding.created_at,
    )


def _latest_reports(reports: list[Report]) -> list[ReportAnalyticsItem]:
    return [
        ReportAnalyticsItem(
            id=report.id,
            investigation_id=report.investigation_id,
            title=report.title,
            report_type=report.report_type,
            status=report.status,
            created_at=report.created_at,
        )
        for report in sorted(
            reports,
            key=lambda item: item.created_at,
            reverse=True,
        )[:5]
    ]


def _investigation_item(
    investigation: Investigation,
) -> InvestigationAnalyticsItem:
    return InvestigationAnalyticsItem(
        id=investigation.id,
        title=investigation.title,
        status=_investigation_status(investigation.status),
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
    )


def _technologies_from_entity(entity: ReconEntity) -> list[str]:
    values: list[str] = []
    if entity.entity_type == "Technology":
        values.append(entity.value)
    for key in ("technology", "technologies", "server", "service"):
        raw = entity.properties.get(key)
        if isinstance(raw, str) and raw.strip():
            values.append(raw.strip())
        elif isinstance(raw, list):
            values.extend(item.strip() for item in raw if isinstance(item, str))
    return [value for value in values if value]


def _first_string(properties: dict[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = properties.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


def _count_strings(values: Iterable[object]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for value in values:
        label = str(value).strip() or "unknown"
        counter[label] += 1
    return dict(sorted(counter.items()))


def _timeline_event_type(event: TimelineEvent | LatestActivityItem) -> str:
    if isinstance(event, TimelineEvent):
        return event.event_type
    return event.id.split(":", 1)[0]


def _top_count_items(counter: Counter[str], limit: int = 5) -> list[CountItem]:
    return [
        CountItem(label=label, count=count)
        for label, count in counter.most_common(limit)
        if label and label != "unknown"
    ]


def _average_confidence(findings: list[Finding]) -> float:
    if not findings:
        return 0.0
    return round(
        sum(finding.confidence_score for finding in findings) / len(findings),
        2,
    )


def _risk_level(score: int) -> RiskLevel:
    if score >= 76:
        return "Critical"
    if score >= 51:
        return "High"
    if score >= 26:
        return "Medium"
    return "Low"


def _finding_severity(value: str) -> FindingSeverity:
    if value in _SEVERITIES:
        return cast(FindingSeverity, value)
    return "info"


def _finding_status(value: str) -> FindingStatus:
    if value in _STATUSES:
        return cast(FindingStatus, value)
    return "new"


def _investigation_status(value: str) -> InvestigationWorkflowStatus:
    if value in _INVESTIGATION_STATUSES:
        return cast(InvestigationWorkflowStatus, value)
    return "active"


def _health_score(
    findings: list[Finding],
    open_tasks: list[InvestigationTask],
    overdue_tasks: list[InvestigationTask],
) -> int:
    score = 100
    score -= sum(
        _SEVERITY_RANK[_finding_severity(finding.severity)] * 3
        for finding in findings
        if _finding_status(finding.status) in _OPEN_STATUSES
    )
    score -= len(open_tasks) * 2
    score -= len(overdue_tasks) * 5
    return max(0, min(100, score))


def _now() -> datetime:
    return datetime.now(UTC)


_OPEN_STATUSES: set[FindingStatus] = {
    "new",
    "under_review",
    "accepted_risk",
    "open",
}
_CLOSED_TASK_STATUSES = {"completed", "cancelled"}
