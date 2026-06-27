from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.investigation_task import InvestigationTask
from app.models.recon_entity import ReconEntity
from app.models.report import Report
from app.models.user import User
from app.schemas.executive import (
    ExecutiveAnalystWorkload,
    ExecutiveDashboardResponse,
    ExecutiveDetectionVisibility,
    ExecutiveFinding,
    ExecutiveInvestigationSummaryResponse,
    ExecutiveKnowledgeUsage,
    ExecutivePostureFactor,
    ExecutivePostureResponse,
    ExecutiveRecommendationItem,
    ExecutiveRecommendationsResponse,
    ExecutiveSignal,
    ExecutiveThreatIntelligence,
    ExecutiveTrendPoint,
    ExecutiveTrendsResponse,
    InvestigationRiskCategory,
    InvestigationRiskScoreResponse,
    RiskScoreContributor,
)
from app.schemas.finding import FindingSeverity
from app.schemas.investigation import InvestigationStage
from app.services.correlation.service import (
    get_cross_investigation_correlations,
)
from app.services.defensive_intelligence import (
    build_coverage_response,
    build_detection_recommendations,
)
from app.services.investigation import get_investigation
from app.services.ioc_intelligence import get_ioc_correlations, list_iocs
from app.services.productivity import get_investigation_readiness
from app.services.threat_workspace import get_threat_overview

_UNRESOLVED_FINDING_STATUSES = {"new", "under_review", "accepted_risk", "open"}
_RESOLVED_REMEDIATION_STATUSES = {
    "remediated",
    "accepted_risk",
    "false_positive",
}
_CLOSED_TASK_STATUSES = {"completed"}
_SEVERITY_POINTS = {
    "critical": 12,
    "high": 8,
    "medium": 4,
    "low": 2,
    "info": 0,
}
_SEVERITY_RANK = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}
_PRIORITY_POINTS = {"low": 0, "medium": 3, "high": 7, "urgent": 10}


class _InvestigationScoped(Protocol):
    investigation_id: uuid.UUID


@dataclass(frozen=True)
class _ExecutiveDataset:
    investigations: list[Investigation]
    findings: list[Finding]
    entities: list[ReconEntity]
    tasks: list[InvestigationTask]
    reports: list[Report]
    members: list[InvestigationMember]


async def get_investigation_risk_score(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> InvestigationRiskScoreResponse:
    investigation = await get_investigation(db, user, investigation_id)
    findings, entities, tasks = await _load_investigation_data(
        db,
        investigation_id,
    )
    correlations = await get_cross_investigation_correlations(db, user)
    recurring_count = sum(
        any(item.investigation_id == investigation_id for item in signal.investigations)
        for signal in correlations.signals
    )
    return _build_risk_score(
        investigation,
        findings,
        entities,
        tasks,
        recurring_count,
    )


async def get_executive_investigation_summary(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> ExecutiveInvestigationSummaryResponse:
    investigation = await get_investigation(db, user, investigation_id)
    findings, entities, tasks = await _load_investigation_data(
        db,
        investigation_id,
    )
    correlations = await get_cross_investigation_correlations(db, user)
    recurring = [
        signal
        for signal in correlations.signals
        if any(
            item.investigation_id == investigation_id
            for item in signal.investigations
        )
    ]
    risk = _build_risk_score(
        investigation,
        findings,
        entities,
        tasks,
        len(recurring),
    )
    readiness = await get_investigation_readiness(db, user, investigation_id)
    unresolved = [
        finding
        for finding in findings
        if finding.status in _UNRESOLVED_FINDING_STATUSES
    ]
    key_findings = sorted(
        unresolved,
        key=lambda item: (
            _SEVERITY_RANK.get(item.severity, 0),
            item.risk_score,
            item.created_at,
        ),
        reverse=True,
    )[:5]
    technologies = sorted(
        {
            value
            for entity in entities
            for value in _technologies_from_entity(entity)
        },
        key=str.lower,
    )
    overdue_tasks = _overdue_tasks(tasks)
    confidence = round(
        sum(item.confidence_score for item in findings) / len(findings)
    ) if findings else 0
    concerns = _defensive_concerns(
        unresolved,
        entities,
        overdue_tasks,
        recurring,
    )
    return ExecutiveInvestigationSummaryResponse(
        investigation_id=investigation.id,
        title=investigation.title,
        objective=(
            investigation.description
            or "Conduct an authorized defensive assessment of stored scope."
        ),
        authorized_scope=(
            investigation.scope_definition
            or "Scope is governed by the stored authorization statement."
        ),
        stage=cast(InvestigationStage, investigation.stage),
        readiness_score=readiness.score,
        readiness_category=readiness.category,
        risk_score=risk.score,
        risk_posture=risk.category,
        status=investigation.status,
        key_findings=[
            ExecutiveFinding(
                id=finding.id,
                title=finding.title,
                severity=cast(FindingSeverity, finding.severity),
                status=finding.status,
                risk_score=finding.risk_score,
                confidence_score=finding.confidence_score,
            )
            for finding in key_findings
        ],
        unresolved_risk=_unresolved_risk_summary(unresolved, risk),
        recurring_issues=[
            f"{signal.value} appears in {signal.investigation_count} investigations."
            for signal in recurring[:5]
        ],
        notable_technologies=technologies[:8],
        business_impact=(
            investigation.business_impact
            or _business_impact_summary(risk, unresolved)
        ),
        defensive_concerns=concerns,
        remediation_urgency=_remediation_urgency(risk, overdue_tasks),
        confidence=confidence,
        generated_at=_now(),
    )


async def get_executive_dashboard(
    db: AsyncSession,
    user: User,
) -> ExecutiveDashboardResponse:
    investigations = await _accessible_investigations(db, user)
    investigation_ids = [item.id for item in investigations]
    findings = await _load_findings(db, investigation_ids)
    entities = await _load_entities(db, investigation_ids)
    tasks = await _load_tasks(db, investigation_ids)
    reports = await _load_reports(db, investigation_ids)
    members = await _load_members(db, investigation_ids)
    correlations = await get_cross_investigation_correlations(db, user)
    findings_by_id = _group_by_investigation(findings)
    entities_by_id = _group_by_investigation(entities)
    tasks_by_id = _group_by_investigation(tasks)
    reports_by_id = _group_by_investigation(reports)
    recurring_by_id: Counter[uuid.UUID] = Counter()
    for signal in correlations.signals:
        for occurrence in signal.investigations:
            recurring_by_id[occurrence.investigation_id] += 1
    risk_by_id = {
        investigation.id: _build_risk_score(
            investigation,
            findings_by_id[investigation.id],
            entities_by_id[investigation.id],
            tasks_by_id[investigation.id],
            recurring_by_id[investigation.id],
        )
        for investigation in investigations
    }
    unresolved_by_id = {
        investigation.id: [
            finding
            for finding in findings_by_id[investigation.id]
            if finding.status in _UNRESOLVED_FINDING_STATUSES
        ]
        for investigation in investigations
    }
    overdue_tasks = _overdue_tasks(tasks)
    usernames = await _usernames(db, {member.user_id for member in members})
    detection_visibility, knowledge_usage = _dashboard_defensive_intelligence(
        investigations,
        findings_by_id,
        entities_by_id,
    )
    ioc_list = await list_iocs(db, user, limit=250)
    ioc_correlations = await get_ioc_correlations(db, user, limit=250)
    threat_overview = await get_threat_overview(db, user)
    correlated_investigations = {
        reference.investigation_id
        for item in ioc_correlations.items
        for reference in item.investigations
    }
    unresolved_correlated_findings = {
        finding.id
        for item in ioc_correlations.items
        for finding in item.related_findings
        if finding.status in _UNRESOLVED_FINDING_STATUSES
    }
    return ExecutiveDashboardResponse(
        generated_at=_now(),
        active_investigations=sum(
            item.status not in {"completed", "archived"} for item in investigations
        ),
        high_risk_investigations=sum(
            item.score >= 61 for item in risk_by_id.values()
        ),
        overdue_remediation=len(overdue_tasks),
        reporting_ready_investigations=sum(
            _is_reporting_ready(item, reports_by_id[item.id])
            for item in investigations
        ),
        investigations_without_remediation=sum(
            bool(unresolved_by_id[item.id]) and not tasks_by_id[item.id]
            for item in investigations
        ),
        investigations_missing_reports=sum(
            not any(report.status == "ready" for report in reports_by_id[item.id])
            for item in investigations
        ),
        recurring_infrastructure=[
            ExecutiveSignal(label=item.value, count=item.investigation_count)
            for item in correlations.signals
            if item.signal_type in {"domain", "subdomain", "ip"}
        ][:6],
        repeated_technologies=[
            ExecutiveSignal(label=item.value, count=item.investigation_count)
            for item in correlations.signals
            if item.signal_type == "technology"
        ][:6],
        repeated_findings=[
            ExecutiveSignal(label=item.value, count=item.investigation_count)
            for item in correlations.signals
            if item.signal_type == "finding"
        ][:6],
        repeated_high_risk_items=_repeated_high_risk_items(findings),
        analyst_workload=_analyst_workload(
            investigations,
            members,
            findings,
            overdue_tasks,
            usernames,
        ),
        detection_visibility=detection_visibility,
        knowledge_usage=knowledge_usage,
        threat_intelligence=ExecutiveThreatIntelligence(
            recurring_infrastructure=ioc_correlations.total,
            recurring_indicators=threat_overview.indicator_count,
            active_campaigns=threat_overview.active_campaigns,
            attack_coverage=threat_overview.attack_coverage,
            repeated_iocs=sum(
                item.investigation_count >= 2 for item in ioc_list.items
            ),
            investigations_sharing_entities=len(correlated_investigations),
            high_confidence_iocs=sum(
                item.confidence == "high" for item in ioc_list.items
            ),
            high_confidence_observations=(
                threat_overview.high_confidence_observations
            ),
            unresolved_correlated_findings=len(unresolved_correlated_findings),
            recent_intelligence_activity=[
                ExecutiveSignal(
                    label=item.value,
                    count=item.observation_count,
                )
                for item in sorted(
                    ioc_list.items,
                    key=lambda ioc: ioc.last_seen,
                    reverse=True,
                )[:6]
            ],
        ),
    )


async def get_executive_posture(
    db: AsyncSession,
    user: User,
) -> ExecutivePostureResponse:
    dataset = await _executive_dataset(db, user)
    active_investigations = sum(
        item.status not in {"completed", "archived"}
        for item in dataset.investigations
    )
    critical_findings = sum(
        item.severity == "critical" and item.status in _UNRESOLVED_FINDING_STATUSES
        for item in dataset.findings
    )
    high_findings = sum(
        item.severity == "high" and item.status in _UNRESOLVED_FINDING_STATUSES
        for item in dataset.findings
    )
    open_remediation = sum(
        item.status not in _CLOSED_TASK_STATUSES for item in dataset.tasks
    )
    overdue_remediation = len(_overdue_tasks(dataset.tasks))
    recurring = await get_cross_investigation_correlations(db, user)
    recurring_signals = len(recurring.signals)
    factors = [
        ExecutivePostureFactor(
            key="critical_findings",
            label="Critical findings",
            value=critical_findings,
            detail="Unresolved critical findings raise executive risk posture.",
        ),
        ExecutivePostureFactor(
            key="high_findings",
            label="High findings",
            value=high_findings,
            detail="Unresolved high findings indicate required analyst follow-up.",
        ),
        ExecutivePostureFactor(
            key="open_remediation",
            label="Open remediation",
            value=open_remediation,
            detail="Open remediation tasks represent remaining defensive work.",
        ),
        ExecutivePostureFactor(
            key="overdue_remediation",
            label="Overdue remediation",
            value=overdue_remediation,
            detail="Overdue remediation increases stakeholder attention.",
        ),
        ExecutivePostureFactor(
            key="recurring_signals",
            label="Recurring signals",
            value=recurring_signals,
            detail="Repeated internal signals can indicate systemic exposure.",
        ),
    ]
    score = min(
        100,
        critical_findings * 18
        + high_findings * 10
        + overdue_remediation * 12
        + open_remediation * 3
        + min(20, recurring_signals * 2),
    )
    return ExecutivePostureResponse(
        generated_at=_now(),
        score=score,
        category=_posture_category(score),
        active_investigations=active_investigations,
        critical_findings=critical_findings,
        high_findings=high_findings,
        open_remediation=open_remediation,
        overdue_remediation=overdue_remediation,
        contributing_factors=factors,
    )


async def get_executive_trends(
    db: AsyncSession,
    user: User,
) -> ExecutiveTrendsResponse:
    dataset = await _executive_dataset(db, user)
    buckets: defaultdict[str, dict[str, int]] = defaultdict(
        lambda: {
            "findings": 0,
            "remediations_completed": 0,
            "investigations_created": 0,
            "reports_generated": 0,
        }
    )
    for finding in dataset.findings:
        buckets[_date_key(finding.created_at)]["findings"] += 1
    for task in dataset.tasks:
        if task.completed_at is not None:
            buckets[_date_key(task.completed_at)]["remediations_completed"] += 1
    for investigation in dataset.investigations:
        buckets[_date_key(investigation.created_at)]["investigations_created"] += 1
    for report in dataset.reports:
        timestamp = report.generated_at or report.created_at
        buckets[_date_key(timestamp)]["reports_generated"] += 1
    cumulative_risk = 0
    points: list[ExecutiveTrendPoint] = []
    for date_key in sorted(buckets):
        values = buckets[date_key]
        cumulative_risk = max(
            0,
            min(
                100,
                cumulative_risk
                + values["findings"] * 5
                - values["remediations_completed"] * 4,
            ),
        )
        points.append(
            ExecutiveTrendPoint(
                date=date_key,
                findings=values["findings"],
                remediations_completed=values["remediations_completed"],
                investigations_created=values["investigations_created"],
                reports_generated=values["reports_generated"],
                risk_score=cumulative_risk,
            )
        )
    if not points:
        summary = "No historical activity is available for executive trend analysis."
    else:
        summary = (
            "Trend is computed from stored findings, completed remediation tasks, "
            "investigations, and generated reports."
        )
    return ExecutiveTrendsResponse(
        generated_at=_now(),
        points=points[-30:],
        summary=summary,
    )


async def get_executive_recommendations(
    db: AsyncSession,
    user: User,
) -> ExecutiveRecommendationsResponse:
    dataset = await _executive_dataset(db, user)
    findings = dataset.findings
    tasks = dataset.tasks
    reports = dataset.reports
    investigations = dataset.investigations
    unresolved_high = [
        item
        for item in findings
        if item.status in _UNRESOLVED_FINDING_STATUSES
        and item.severity in {"critical", "high"}
    ]
    overdue = _overdue_tasks(tasks)
    recommendations: list[ExecutiveRecommendationItem] = []
    if unresolved_high:
        recommendations.append(
            ExecutiveRecommendationItem(
                category="Immediate",
                title="Prioritize unresolved high-risk findings",
                recommendation=(
                    "Assign owners and confirm remediation plans for critical "
                    "and high severity evidence-backed findings."
                ),
                evidence_refs=[f"finding:{item.id}" for item in unresolved_high[:5]],
                related_findings=[item.id for item in unresolved_high[:5]],
                related_investigations=list(
                    {item.investigation_id for item in unresolved_high[:5]}
                ),
            )
        )
    if overdue:
        recommendations.append(
            ExecutiveRecommendationItem(
                category="Immediate",
                title="Resolve overdue remediation ownership",
                recommendation=(
                    "Review overdue remediation tasks and reset accountability "
                    "with the responsible investigation owners."
                ),
                evidence_refs=[f"task:{item.id}" for item in overdue[:5]],
                related_investigations=list(
                    {item.investigation_id for item in overdue[:5]}
                ),
            )
        )
    investigations_without_reports = [
        item
        for item in investigations
        if item.status != "archived"
        and not any(report.investigation_id == item.id for report in reports)
    ]
    if investigations_without_reports:
        recommendations.append(
            ExecutiveRecommendationItem(
                category="Short-Term",
                title="Generate stakeholder-ready reports",
                recommendation=(
                    "Create executive or management reports for active "
                    "investigations that already have stored evidence."
                ),
                evidence_refs=[
                    f"investigation:{item.id}"
                    for item in investigations_without_reports[:5]
                ],
                related_investigations=[
                    item.id for item in investigations_without_reports[:5]
                ],
            )
        )
    recurring = await get_cross_investigation_correlations(db, user)
    if recurring.signals:
        recommendations.append(
            ExecutiveRecommendationItem(
                category="Long-Term",
                title="Review recurring infrastructure patterns",
                recommendation=(
                    "Use recurring internal correlation signals to identify "
                    "repeat exposure themes and standardize defensive controls."
                ),
                evidence_refs=[
                    f"correlation:{item.signal_type}:{item.value}"
                    for item in recurring.signals[:5]
                ],
                related_investigations=list(
                    {
                        reference.investigation_id
                        for item in recurring.signals[:5]
                        for reference in item.investigations
                    }
                ),
            )
        )
    if not recommendations:
        recommendations.append(
            ExecutiveRecommendationItem(
                category="Long-Term",
                title="Maintain evidence-backed governance cadence",
                recommendation=(
                    "Continue periodic defensive review, report generation, "
                    "and remediation tracking as investigations mature."
                ),
            )
        )
    return ExecutiveRecommendationsResponse(
        generated_at=_now(),
        items=recommendations,
    )


def _build_risk_score(
    investigation: Investigation,
    findings: list[Finding],
    entities: list[ReconEntity],
    tasks: list[InvestigationTask],
    recurring_count: int,
) -> InvestigationRiskScoreResponse:
    unresolved = [
        finding
        for finding in findings
        if finding.status in _UNRESOLVED_FINDING_STATUSES
    ]
    severity_points = min(
        30,
        sum(_SEVERITY_POINTS.get(finding.severity, 0) for finding in unresolved),
    )
    unresolved_points = min(15, len(unresolved) * 3)
    service_count = sum(entity.entity_type == "Service" for entity in entities)
    service_points = min(10, service_count * 2)
    recurring_points = min(10, recurring_count * 2)
    resolved_count = sum(
        finding.remediation_status in _RESOLVED_REMEDIATION_STATUSES
        or finding.status in {"mitigated", "resolved", "false_positive"}
        for finding in findings
    )
    remediation_points = (
        round((1 - (resolved_count / len(findings))) * 15) if findings else 0
    )
    overdue_count = len(_overdue_tasks(tasks))
    overdue_points = min(10, overdue_count * 5)
    priority_points = _PRIORITY_POINTS.get(investigation.priority, 3)
    contributors = [
        RiskScoreContributor(
            key="finding_severity",
            label="Finding severity",
            points=severity_points,
            max_points=30,
            detail=f"{len(unresolved)} unresolved findings weighted by severity.",
        ),
        RiskScoreContributor(
            key="unresolved_findings",
            label="Unresolved findings",
            points=unresolved_points,
            max_points=15,
            detail=f"{len(unresolved)} findings remain unresolved.",
        ),
        RiskScoreContributor(
            key="exposed_services",
            label="Observed services",
            points=service_points,
            max_points=10,
            detail=f"{service_count} service entities are stored.",
        ),
        RiskScoreContributor(
            key="recurring_evidence",
            label="Recurring evidence",
            points=recurring_points,
            max_points=10,
            detail=f"{recurring_count} signals recur across accessible cases.",
        ),
        RiskScoreContributor(
            key="remediation_completion",
            label="Remediation gap",
            points=remediation_points,
            max_points=15,
            detail=f"{resolved_count} of {len(findings)} findings are resolved.",
        ),
        RiskScoreContributor(
            key="overdue_remediation",
            label="Overdue remediation",
            points=overdue_points,
            max_points=10,
            detail=f"{overdue_count} remediation tasks are overdue.",
        ),
        RiskScoreContributor(
            key="investigation_priority",
            label="Investigation priority",
            points=priority_points,
            max_points=10,
            detail=f"Priority is {investigation.priority}.",
        ),
    ]
    score = min(100, sum(item.points for item in contributors))
    return InvestigationRiskScoreResponse(
        investigation_id=investigation.id,
        score=score,
        category=_risk_category(score),
        contributors=contributors,
        generated_at=_now(),
    )


def _risk_category(score: int) -> InvestigationRiskCategory:
    if score <= 20:
        return "Low Risk"
    if score <= 40:
        return "Moderate Risk"
    if score <= 60:
        return "Elevated Risk"
    if score <= 80:
        return "High Risk"
    return "Critical Risk"


def _unresolved_risk_summary(
    findings: list[Finding],
    risk: InvestigationRiskScoreResponse,
) -> str:
    if not findings:
        return "No unresolved evidence-backed findings are currently stored."
    high = sum(item.severity in {"critical", "high"} for item in findings)
    return (
        f"{len(findings)} findings remain unresolved, including {high} high or "
        f"critical items. Deterministic posture is {risk.category.lower()}."
    )


def _business_impact_summary(
    risk: InvestigationRiskScoreResponse,
    findings: list[Finding],
) -> str:
    if not findings:
        return (
            "No validated business impact is currently established from stored "
            "evidence."
        )
    return (
        f"Stored evidence indicates a {risk.category.lower()} defensive posture. "
        "Operational impact should be validated with the authorized asset owner."
    )


def _defensive_concerns(
    findings: list[Finding],
    entities: list[ReconEntity],
    overdue_tasks: list[InvestigationTask],
    recurring: Sequence[object],
) -> list[str]:
    concerns: list[str] = []
    if any(item.severity in {"critical", "high"} for item in findings):
        concerns.append("High-severity findings require documented analyst review.")
    service_count = sum(item.entity_type == "Service" for item in entities)
    if service_count:
        concerns.append(
            f"{service_count} observed services require authorized exposure review."
        )
    if overdue_tasks:
        concerns.append(
            f"{len(overdue_tasks)} remediation tasks are beyond their due date."
        )
    if recurring:
        concerns.append(
            "Stored infrastructure or evidence recurs across accessible cases."
        )
    return concerns or ["No elevated defensive concern is established yet."]


def _remediation_urgency(
    risk: InvestigationRiskScoreResponse,
    overdue_tasks: list[InvestigationTask],
) -> str:
    if overdue_tasks or risk.score >= 81:
        return "Immediate analyst review and remediation ownership are recommended."
    if risk.score >= 61:
        return "Prioritize remediation planning in the current review cycle."
    if risk.score >= 41:
        return "Track remediation and validate outstanding evidence."
    return "Continue routine monitoring and evidence validation."


def _technologies_from_entity(entity: ReconEntity) -> list[str]:
    values: list[str] = []
    if entity.entity_type == "Technology":
        values.append(entity.value)
    for key in ("technology", "technologies", "server", "service"):
        raw = entity.properties.get(key)
        if isinstance(raw, str) and raw.strip():
            values.append(raw.strip())
        elif isinstance(raw, list):
            values.extend(
                value.strip()
                for value in raw
                if isinstance(value, str) and value.strip()
            )
    return values


async def _load_investigation_data(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> tuple[list[Finding], list[ReconEntity], list[InvestigationTask]]:
    return (
        await _load_findings(db, [investigation_id]),
        await _load_entities(db, [investigation_id]),
        await _load_tasks(db, [investigation_id]),
    )


async def _accessible_investigations(
    db: AsyncSession,
    user: User,
) -> list[Investigation]:
    statement = select(Investigation)
    if user.role != "admin":
        statement = statement.join(
            InvestigationMember,
            InvestigationMember.investigation_id == Investigation.id,
        ).where(InvestigationMember.user_id == user.id)
    result = await db.execute(statement)
    return list(result.scalars().unique().all())


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


async def _load_entities(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[ReconEntity]:
    if not investigation_ids:
        return []
    result = await db.execute(
        select(ReconEntity).where(
            ReconEntity.investigation_id.in_(investigation_ids)
        )
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
            InvestigationTask.investigation_id.in_(investigation_ids),
            InvestigationTask.archived_at.is_(None),
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


async def _load_members(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[InvestigationMember]:
    if not investigation_ids:
        return []
    result = await db.execute(
        select(InvestigationMember).where(
            InvestigationMember.investigation_id.in_(investigation_ids)
        )
    )
    return list(result.scalars().all())


async def _executive_dataset(
    db: AsyncSession,
    user: User,
) -> _ExecutiveDataset:
    investigations = await _accessible_investigations(db, user)
    investigation_ids = [item.id for item in investigations]
    return _ExecutiveDataset(
        investigations=investigations,
        findings=await _load_findings(db, investigation_ids),
        entities=await _load_entities(db, investigation_ids),
        tasks=await _load_tasks(db, investigation_ids),
        reports=await _load_reports(db, investigation_ids),
        members=await _load_members(db, investigation_ids),
    )


async def _usernames(
    db: AsyncSession,
    user_ids: set[uuid.UUID],
) -> dict[uuid.UUID, str]:
    if not user_ids:
        return {}
    result = await db.execute(select(User).where(User.id.in_(user_ids)))
    return {item.id: item.username for item in result.scalars().all()}


def _group_by_investigation[InvestigationScopedT: _InvestigationScoped](
    items: Sequence[InvestigationScopedT],
) -> defaultdict[uuid.UUID, list[InvestigationScopedT]]:
    grouped: defaultdict[uuid.UUID, list[InvestigationScopedT]] = defaultdict(list)
    for item in items:
        grouped[item.investigation_id].append(item)
    return grouped


def _overdue_tasks(
    tasks: list[InvestigationTask],
) -> list[InvestigationTask]:
    now = _now()
    return [
        task
        for task in tasks
        if task.status not in _CLOSED_TASK_STATUSES
        and task.due_date is not None
        and task.due_date < now
    ]


def _is_reporting_ready(
    investigation: Investigation,
    reports: list[Report],
) -> bool:
    return investigation.stage in {"reporting", "completed"} or any(
        report.status == "ready" for report in reports
    )


def _analyst_workload(
    investigations: list[Investigation],
    members: list[InvestigationMember],
    findings: list[Finding],
    overdue_tasks: list[InvestigationTask],
    usernames: dict[uuid.UUID, str],
) -> list[ExecutiveAnalystWorkload]:
    investigation_ids_by_user: defaultdict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for member in members:
        if member.role in {"owner", "admin", "analyst"}:
            investigation_ids_by_user[member.user_id].add(member.investigation_id)
    for investigation in investigations:
        investigation_ids_by_user[investigation.owner_id].add(investigation.id)
    unresolved_by_user = Counter(
        finding.assigned_to
        for finding in findings
        if finding.assigned_to is not None
        and finding.status in _UNRESOLVED_FINDING_STATUSES
    )
    overdue_by_user = Counter(
        task.assigned_to
        for task in overdue_tasks
        if task.assigned_to is not None
    )
    items = [
        ExecutiveAnalystWorkload(
            user_id=user_id,
            analyst_name=usernames.get(user_id, str(user_id)),
            investigations=len(investigation_ids),
            overdue_ownership=overdue_by_user[user_id],
            unresolved_findings=unresolved_by_user[user_id],
        )
        for user_id, investigation_ids in investigation_ids_by_user.items()
    ]
    return sorted(
        items,
        key=lambda item: (
            item.overdue_ownership,
            item.unresolved_findings,
            item.investigations,
        ),
        reverse=True,
    )[:10]


def _repeated_high_risk_items(findings: Sequence[Finding]) -> list[ExecutiveSignal]:
    counts: Counter[str] = Counter(
        finding.title
        for finding in findings
        if finding.status in _UNRESOLVED_FINDING_STATUSES
        and finding.severity in {"critical", "high"}
    )
    return [
        ExecutiveSignal(label=label, count=count)
        for label, count in counts.most_common(6)
        if count >= 1
    ]


def _dashboard_defensive_intelligence(
    investigations: list[Investigation],
    findings_by_id: defaultdict[uuid.UUID, list[Finding]],
    entities_by_id: defaultdict[uuid.UUID, list[ReconEntity]],
) -> tuple[ExecutiveDetectionVisibility, ExecutiveKnowledgeUsage]:
    mapped_findings = 0
    total_findings = 0
    gap_counts: Counter[str] = Counter()
    framework_counts: Counter[str] = Counter()
    concern_counts: Counter[str] = Counter()
    for investigation in investigations:
        findings = findings_by_id[investigation.id]
        recommendations = build_detection_recommendations(
            findings,
            entities_by_id[investigation.id],
        )
        coverage = build_coverage_response(
            investigation.id,
            findings,
            recommendations,
        )
        total_findings += coverage.total_findings
        mapped_findings += coverage.mapped_findings
        gap_counts.update(coverage.missing_defensive_visibility)
        framework_counts.update(coverage.framework_counts)
        concern_counts.update(
            item.why_this_matters for item in recommendations
        )
    coverage_percent = (
        round((mapped_findings / total_findings) * 100)
        if total_findings
        else 0
    )
    return (
        ExecutiveDetectionVisibility(
            mapped_findings=mapped_findings,
            missing_coverage=max(0, total_findings - mapped_findings),
            coverage_percent=coverage_percent,
            recurring_defensive_gaps=[
                ExecutiveSignal(label=label, count=count)
                for label, count in gap_counts.most_common(6)
            ],
        ),
        ExecutiveKnowledgeUsage(
            most_referenced_frameworks=[
                ExecutiveSignal(label=label, count=count)
                for label, count in framework_counts.most_common(6)
            ],
            common_defensive_concerns=[
                ExecutiveSignal(label=label, count=count)
                for label, count in concern_counts.most_common(6)
            ],
        ),
    )


def _now() -> datetime:
    return datetime.now(UTC)


def _posture_category(score: int) -> Literal["Low", "Medium", "High", "Critical"]:
    if score >= 81:
        return "Critical"
    if score >= 61:
        return "High"
    if score >= 31:
        return "Medium"
    return "Low"


def _date_key(value: datetime) -> str:
    return value.date().isoformat()
