from __future__ import annotations

import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.finding_tag import FindingTag
from app.models.user import User
from app.schemas.finding import (
    FindingEvidenceResponse,
    FindingResponse,
    FindingSeverity,
    FindingStatus,
    FindingSummaryResponse,
)
from app.services.intelligence.correlation_service import (
    generate_findings_for_investigation,
)
from app.services.intelligence.risk_engine import (
    RiskCategory,
    RiskSignal,
    calculate_risk_v2,
)
from app.services.investigation import get_investigation


class FindingNotFoundError(Exception):
    pass


async def list_findings_for_investigation(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    *,
    severity: FindingSeverity | None = None,
    status: FindingStatus | None = None,
    source: str | None = None,
) -> list[FindingResponse]:
    await get_investigation(db, user, investigation_id)
    await generate_findings_for_investigation(db, user, investigation_id)
    filters = [Finding.investigation_id == investigation_id]
    if severity is not None:
        filters.append(Finding.severity == severity)
    if status is not None:
        filters.append(Finding.status == status)
    if source is not None:
        filters.append(Finding.source == source)

    result = await db.execute(
        select(Finding)
        .where(*filters)
        .order_by(Finding.risk_score.desc(), Finding.created_at.desc())
    )
    return await _build_finding_responses(db, list(result.scalars().all()))


async def summarize_findings_for_investigation(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> FindingSummaryResponse:
    await get_investigation(db, user, investigation_id)
    await generate_findings_for_investigation(db, user, investigation_id)
    result = await db.execute(
        select(Finding).where(Finding.investigation_id == investigation_id)
    )
    findings = list(result.scalars().all())
    severity_counts: Counter[str] = Counter(finding.severity for finding in findings)
    status_counts: Counter[str] = Counter(finding.status for finding in findings)
    source_counts: Counter[str] = Counter(finding.source for finding in findings)
    assessment = calculate_risk_v2(_risk_signals_from_findings(findings))
    return FindingSummaryResponse(
        investigation_id=investigation_id,
        total=len(findings),
        by_severity={
            severity: severity_counts.get(severity, 0)
            for severity in _FINDING_SEVERITIES
        },
        by_status={
            status: status_counts.get(status, 0) for status in _FINDING_STATUSES
        },
        by_source=dict(source_counts),
        risk_score_v2=assessment.score,
        risk_level_v2=assessment.band,
        risk_signals=assessment.signals,
    )


async def update_finding_status(
    db: AsyncSession,
    user: User,
    finding_id: uuid.UUID,
    status: FindingStatus,
) -> FindingResponse:
    finding = await db.get(Finding, finding_id)
    if finding is None:
        raise FindingNotFoundError("Finding not found")
    await get_investigation(db, user, finding.investigation_id)
    finding.status = status
    db.add(finding)
    await db.flush()
    await db.refresh(finding)
    responses = await _build_finding_responses(db, [finding])
    return responses[0]


async def _build_finding_responses(
    db: AsyncSession,
    findings: list[Finding],
) -> list[FindingResponse]:
    if not findings:
        return []
    finding_ids = [finding.id for finding in findings]
    evidence_result = await db.execute(
        select(FindingEvidence)
        .where(FindingEvidence.finding_id.in_(finding_ids))
        .order_by(FindingEvidence.created_at)
    )
    tag_result = await db.execute(
        select(FindingTag)
        .where(FindingTag.finding_id.in_(finding_ids))
        .order_by(FindingTag.tag)
    )
    evidence_by_finding: dict[uuid.UUID, list[FindingEvidence]] = {}
    for evidence in evidence_result.scalars().all():
        evidence_by_finding.setdefault(evidence.finding_id, []).append(evidence)

    tags_by_finding: dict[uuid.UUID, list[str]] = {}
    for tag in tag_result.scalars().all():
        tags_by_finding.setdefault(tag.finding_id, []).append(tag.tag)

    return [
        FindingResponse(
            id=finding.id,
            investigation_id=finding.investigation_id,
            title=finding.title,
            description=finding.description,
            severity=finding.severity,  # type: ignore[arg-type]
            confidence_score=finding.confidence_score,
            risk_score=finding.risk_score,
            source=finding.source,
            status=finding.status,  # type: ignore[arg-type]
            created_by=finding.created_by,
            created_at=finding.created_at,
            updated_at=finding.updated_at,
            evidence=[
                FindingEvidenceResponse.model_validate(evidence)
                for evidence in evidence_by_finding.get(finding.id, [])
            ],
            tags=tags_by_finding.get(finding.id, []),
        )
        for finding in findings
    ]


def _risk_signals_from_findings(findings: list[Finding]) -> list[RiskSignal]:
    signals: list[RiskSignal] = []
    for finding in findings:
        category = _risk_category_for_finding(finding)
        if category is None:
            continue
        signals.append(
            RiskSignal(
                category=category,
                score=finding.risk_score,
                description=finding.title,
            )
        )
    return signals


def _risk_category_for_finding(finding: Finding) -> RiskCategory | None:
    if finding.source == "virustotal":
        return "virustotal"
    if finding.source == "abuseipdb":
        return "abuseipdb"
    if finding.source == "tls":
        return "tls_health"
    if finding.source == "certificate":
        return "certificate_anomalies"
    if finding.source == "http" and "server disclosure" in finding.title.lower():
        return "suspicious_technologies"
    if finding.source in ("http", "dns"):
        return "security_headers"
    return None


_FINDING_SEVERITIES: tuple[FindingSeverity, ...] = (
    "info",
    "low",
    "medium",
    "high",
    "critical",
)
_FINDING_STATUSES: tuple[FindingStatus, ...] = (
    "open",
    "validated",
    "false_positive",
    "resolved",
)
