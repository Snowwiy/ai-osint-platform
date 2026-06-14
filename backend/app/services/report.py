from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.evidence_bookmark import EvidenceBookmark
from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.investigation_evidence import InvestigationEvidence
from app.models.investigation_note import InvestigationNote
from app.models.investigation_task import InvestigationTask
from app.models.investigation_tag import InvestigationTag, InvestigationTagLink
from app.models.investigation_workflow_event import InvestigationWorkflowEvent
from app.models.playbook import (
    DefensivePlaybook,
    PlaybookRun,
    PlaybookRunStep,
    PlaybookStep,
)
from app.models.recon_entity import ReconEntity
from app.models.report import Report
from app.models.threat_finding import ThreatFinding
from app.models.user import User
from app.schemas.report import ReportCreateRequest
from app.services.ai.evidence_builder import EvidenceItem
from app.services.ai.framework_mapper import map_frameworks
from app.services.investigation import MUTATION_ROLES, ensure_investigation_permission, get_investigation
from app.services.knowledge.retriever import KnowledgeCitation, retrieve_context

logger = logging.getLogger(__name__)


class ReportNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class PlaybookStepContext:
    title: str
    step_type: str
    status: str
    analyst_note: str | None
    expected_output: str | None


@dataclass(frozen=True)
class PlaybookRunContext:
    id: uuid.UUID
    finding_id: uuid.UUID
    playbook_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    completed_steps: int
    total_steps: int
    steps: list[PlaybookStepContext]


@dataclass(frozen=True)
class ReportContext:
    investigation: Investigation
    report_type: str
    findings: list[Finding]
    evidence: list[FindingEvidence]
    case_evidence: list[InvestigationEvidence]
    notes: list[InvestigationNote]
    tasks: list[InvestigationTask]
    workflow_events: list[InvestigationWorkflowEvent]
    audit_events: list[AuditLog]
    members: list[InvestigationMember]
    playbook_runs: list[PlaybookRunContext]
    bookmarks: list[EvidenceBookmark]
    tags: list[InvestigationTag]
    recon_entities: list[ReconEntity]
    threat_findings: list[ThreatFinding]
    knowledge_citations: list[KnowledgeCitation]
    framework_mappings: list[dict[str, object]]
    recommendations: list[str]
    risk_summary: dict[str, object]
    analysis_summary: str
    business_impact: str
    severity_heatmap: dict[str, int]
    indicator_summary: list[str]
    evidence_chain: list[str]
    analyst_notes: list[str]
    remediation_progress: dict[str, int]


async def create_report(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    body: ReportCreateRequest,
) -> Report:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot generate reports",
    )
    context = await _build_context(db, investigation, body.report_type)
    markdown = render_markdown_report(context)
    html = render_html_report(context)
    title = body.title or f"{investigation.title} {body.report_type.title()} Report"
    report = Report(
        investigation_id=investigation_id,
        generated_by=user.id,
        title=title,
        report_type=body.report_type,
        report_format="html",
        status="ready",
        html_content=html,
        markdown_content=markdown,
        file_size_bytes=len(html.encode("utf-8")) + len(markdown.encode("utf-8")),
        report_metadata=_metadata(context),
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report


async def list_reports(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[Report]:
    await get_investigation(db, user, investigation_id)
    result = await db.execute(
        select(Report)
        .where(Report.investigation_id == investigation_id)
        .order_by(Report.created_at.desc())
    )
    return list(result.scalars().all())


async def get_report(
    db: AsyncSession,
    user: User,
    report_id: uuid.UUID,
) -> Report:
    report = await db.get(Report, report_id)
    if report is None:
        raise ReportNotFoundError("Report not found")
    await get_investigation(db, user, report.investigation_id)
    return report


def render_html_report(context: ReportContext) -> str:
    template_dir = Path(__file__).resolve().parents[1] / "templates" / "reports"
    environment = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template("report.html.j2")
    return template.render(context=context)


def render_markdown_report(context: ReportContext) -> str:
    lines = [
        f"# {context.investigation.title} {context.report_type.title()} Report",
        "",
        "## Executive Summary",
        "",
        context.analysis_summary,
        "",
        f"Workflow status: {context.investigation.status}",
        f"Case owner: {context.investigation.owner_id}",
        f"Reviewer: {context.investigation.reviewer_id or 'Unassigned'}",
        f"Members: {len(context.members)}",
        f"Priority: {context.investigation.priority}",
        (
            "Due date: "
            f"{context.investigation.due_date or 'No investigation due date set'}"
        ),
        "Tags: " + (", ".join(tag.name for tag in context.tags) or "None"),
        "",
        "### Business Impact",
        "",
        context.business_impact,
        "",
        "### Severity Heatmap",
        "",
        f"- Critical: {context.severity_heatmap['critical']}",
        f"- High: {context.severity_heatmap['high']}",
        f"- Medium: {context.severity_heatmap['medium']}",
        f"- Low: {context.severity_heatmap['low']}",
        f"- Info: {context.severity_heatmap['info']}",
        f"- Risk score: {context.risk_summary['highest_score']}",
        f"- Open remediation tasks: {context.remediation_progress['open']}",
        f"- Validated findings: {context.remediation_progress['validated_findings']}",
        f"- Unresolved findings: {context.remediation_progress['unresolved_findings']}",
        f"- Accepted risks: {context.remediation_progress['accepted_risk_findings']}",
        f"- Completed playbooks: {context.remediation_progress['playbooks_completed']}",
        "",
        "## Scope and Authorization",
        "",
        f"Authorization: {context.investigation.authorization_statement}",
        "",
        f"Scope: {context.investigation.scope_definition or 'No scope note provided.'}",
        "",
        "## Methodology",
        "",
        (
            "This report uses stored passive recon entities, threat intelligence "
            "findings, correlation findings, and local defensive knowledge citations."
        ),
        "",
        "## Key Findings",
        "",
    ]
    if context.findings:
        for finding in context.findings:
            lines.extend(
                [
                    f"- **{finding.severity.upper()}** {finding.title} "
                    f"(risk {finding.risk_score}, confidence "
                    f"{finding.confidence_score})",
                ]
            )
    else:
        lines.append("- No correlation findings are currently stored.")

    lines.extend(
        [
            "",
            "## Risk Summary",
            "",
            f"- Overall level: {context.risk_summary['level']}",
            f"- Highest score: {context.risk_summary['highest_score']}",
            f"- Finding count: {context.risk_summary['finding_count']}",
            "",
            "## Technical Evidence",
            "",
        ]
    )
    if context.evidence:
        for item in context.evidence:
            lines.append(f"- {item.source}: {item.description}")
    else:
        lines.append("- No technical evidence records are currently stored.")

    if context.report_type == "technical":
        lines.extend(["", "### Indicators and Entities", ""])
        if context.indicator_summary:
            for indicator in context.indicator_summary:
                lines.append(f"- {indicator}")
        else:
            lines.append("- No recon entities or threat indicators are stored.")
        lines.extend(["", "### Evidence Chain", ""])
        if context.evidence_chain:
            for evidence in context.evidence_chain:
                lines.append(f"- {evidence}")
        else:
            lines.append("- No linked evidence chain records are stored.")
        lines.extend(["", "### Analyst Notes", ""])
        if context.analyst_notes:
            for note in context.analyst_notes:
                lines.append(f"- {note}")
        else:
            lines.append("- No active analyst notes are stored.")
        lines.extend(["", "### Bookmarked Evidence", ""])
        if context.bookmarks:
            for bookmark in context.bookmarks:
                reference = (
                    bookmark.entity_id or bookmark.finding_id or bookmark.report_id
                )
                lines.append(
                    f"- {bookmark.title}: {reference}"
                    + (f" - {bookmark.note}" if bookmark.note else "")
                )
        else:
            lines.append("- No evidence bookmarks are currently stored.")
        lines.extend(["", "### Workflow History", ""])
        if context.workflow_events:
            for event in context.workflow_events[:10]:
                lines.append(
                    f"- {event.created_at}: {event.from_status or 'new'} "
                    f"-> {event.to_status}"
                )
        else:
            lines.append("- No workflow history events are stored.")
        lines.extend(["", "### Audit Summary", ""])
        if context.audit_events:
            for audit_event in context.audit_events[:10]:
                lines.append(
                    f"- {audit_event.created_at}: {audit_event.action} "
                    f"on {audit_event.resource_type or 'resource'}"
                )
        else:
            lines.append("- No investigation-scoped audit events are stored.")
        lines.extend(["", "### Case Evidence", ""])
        if context.case_evidence:
            for case_item in context.case_evidence:
                lines.append(
                    f"- {case_item.evidence_type}: {case_item.title} "
                    f"(review {case_item.review_status}, "
                    f"confidence {case_item.confidence_score})"
                )
        else:
            lines.append("- No case evidence metadata records are stored.")

    lines.extend(["", "## Remediation Tracking", ""])
    lines.extend(
        [
            f"- Total tasks: {context.remediation_progress['total']}",
            f"- Completed tasks: {context.remediation_progress['completed']}",
            f"- Blocked tasks: {context.remediation_progress['blocked']}",
            f"- Open tasks: {context.remediation_progress['open']}",
            f"- Overdue tasks: {context.remediation_progress['overdue']}",
        ]
    )
    if context.tasks:
        for task in context.tasks[:10]:
            lines.append(f"- {task.status}: {task.title} ({task.priority})")
    lines.extend(["", "### Defensive Playbook Progress", ""])
    if context.playbook_runs:
        for playbook_run in context.playbook_runs[:10]:
            completed_steps = sum(
                1
                for step in playbook_run.steps
                if step.status in {"completed", "skipped"}
            )
            lines.append(
                f"- {playbook_run.playbook_name}: {playbook_run.status} "
                f"({completed_steps}/{len(playbook_run.steps)} steps)"
            )
            if context.report_type == "technical":
                for step in playbook_run.steps:
                    note = f" - {step.analyst_note}" if step.analyst_note else ""
                    lines.append(
                        f"  - {step.status}: {step.title} "
                        f"[{step.step_type}]{note}"
                    )
    else:
        lines.append("- No defensive playbook runs are stored.")
    if context.report_type == "technical":
        lines.extend(["", "### Finding Verification Notes", ""])
        verification_items = [
            finding
            for finding in context.findings
            if finding.verification_notes or finding.remediation_notes
        ]
        if verification_items:
            for finding in verification_items:
                lines.append(
                    f"- {finding.title}: remediation "
                    f"{finding.remediation_status}; "
                    f"{finding.verification_notes or finding.remediation_notes}"
                )
        else:
            lines.append("- No finding verification notes are stored.")
    if context.report_type == "executive":
        executive_notes = [
            case_note
            for case_note in context.notes
            if case_note.note_type == "executive_note"
        ]
        lines.extend(["", "### Analyst Summary and Recommendations", ""])
        if executive_notes:
            for executive_note in executive_notes[:8]:
                lines.append(f"- {executive_note.title}: {executive_note.content}")
        else:
            lines.append("- No executive analyst notes are currently stored.")

    lines.extend(["", "## MITRE/OWASP/NIST/ISO Mapping", ""])
    if context.framework_mappings:
        for mapping in context.framework_mappings:
            lines.append(
                f"- {mapping['framework']}: {mapping['control']} - "
                f"{mapping['rationale']}"
            )
    else:
        lines.append("- No framework mappings were derived from stored evidence.")

    lines.extend(["", "## Recommendations", ""])
    for recommendation in context.recommendations:
        lines.append(f"- {recommendation}")

    lines.extend(["", "## Appendix", ""])
    lines.extend(
        [
            f"- Recon entities: {len(context.recon_entities)}",
            f"- Threat intel findings: {len(context.threat_findings)}",
            f"- Analyst notes: {len(context.notes)}",
            f"- Bookmarked evidence: {len(context.bookmarks)}",
            f"- Investigation tags: {len(context.tags)}",
            f"- Case evidence records: {len(context.case_evidence)}",
            f"- Investigation members: {len(context.members)}",
            f"- Knowledge citations: {len(context.knowledge_citations)}",
        ]
    )
    if context.members:
        lines.extend(["", "### Collaboration Summary", ""])
        for member in context.members:
            lines.append(f"- {member.role}: {member.user_id}")
    if context.knowledge_citations:
        lines.extend(["", "### Knowledge Citations", ""])
        for citation in context.knowledge_citations:
            lines.append(
                f"- [{citation.id}] {citation.framework}: {citation.title} "
                f"({citation.source})"
            )
    return "\n".join(lines).strip() + "\n"


async def _build_context(
    db: AsyncSession,
    investigation: Investigation,
    report_type: str,
) -> ReportContext:
    findings = await _findings(db, investigation.id)
    evidence = await _finding_evidence(db, [finding.id for finding in findings])
    recon_entities = await _recon_entities(db, investigation.id)
    threat_findings = await _threat_findings(db, investigation.id)
    notes = await _notes(db, investigation.id)
    tasks = await _tasks(db, investigation.id)
    case_evidence = await _case_evidence(db, investigation.id)
    workflow_events = await _workflow_events(db, investigation.id)
    audit_events = await _audit_events(db, investigation.id)
    members = await _members(db, investigation.id)
    playbook_runs = await _playbook_runs(db, investigation.id)
    bookmarks = await _bookmarks(db, investigation.id)
    tags = await _tags(db, investigation.id)
    knowledge_citations = _knowledge_citations(findings, recon_entities)
    evidence_items = _evidence_items(findings)
    knowledge_items = _knowledge_items(knowledge_citations)
    mappings = [
        mapping.model_dump()
        for mapping in map_frameworks(evidence_items, knowledge_items)
    ]
    return ReportContext(
        investigation=investigation,
        report_type=report_type,
        findings=findings,
        evidence=evidence,
        case_evidence=case_evidence,
        notes=notes,
        tasks=tasks,
        workflow_events=workflow_events,
        audit_events=audit_events,
        members=members,
        playbook_runs=playbook_runs,
        bookmarks=bookmarks,
        tags=tags,
        recon_entities=recon_entities,
        threat_findings=threat_findings,
        knowledge_citations=knowledge_citations,
        framework_mappings=mappings,
        recommendations=_recommendations(findings, knowledge_citations),
        risk_summary=_risk_summary(findings),
        analysis_summary=_analysis_summary(findings),
        business_impact=investigation.business_impact or _business_impact(findings),
        severity_heatmap=_severity_heatmap(findings),
        indicator_summary=_indicator_summary(recon_entities, threat_findings),
        evidence_chain=_evidence_chain(evidence, case_evidence),
        analyst_notes=_analyst_notes(notes),
        remediation_progress=_remediation_progress(tasks, findings, playbook_runs),
    )


async def _findings(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[Finding]:
    result = await db.execute(
        select(Finding)
        .where(Finding.investigation_id == investigation_id)
        .order_by(Finding.risk_score.desc(), Finding.created_at.desc())
    )
    return list(result.scalars().all())


async def _notes(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[InvestigationNote]:
    result = await db.execute(
        select(InvestigationNote)
        .where(
            InvestigationNote.investigation_id == investigation_id,
            InvestigationNote.archived.is_(False),
        )
        .order_by(
            InvestigationNote.pinned.desc(),
            InvestigationNote.updated_at.desc(),
        )
    )
    return list(result.scalars().all())


async def _bookmarks(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[EvidenceBookmark]:
    result = await db.execute(
        select(EvidenceBookmark)
        .where(EvidenceBookmark.investigation_id == investigation_id)
        .order_by(EvidenceBookmark.created_at.desc())
    )
    return list(result.scalars().all())


async def _tags(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[InvestigationTag]:
    result = await db.execute(
        select(InvestigationTag)
        .join(
            InvestigationTagLink,
            InvestigationTagLink.tag_id == InvestigationTag.id,
        )
        .where(InvestigationTagLink.investigation_id == investigation_id)
        .order_by(InvestigationTag.name)
    )
    return list(result.scalars().all())


async def _members(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[InvestigationMember]:
    result = await db.execute(
        select(InvestigationMember)
        .where(InvestigationMember.investigation_id == investigation_id)
        .order_by(InvestigationMember.role, InvestigationMember.created_at)
    )
    return list(result.scalars().all())


async def _tasks(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[InvestigationTask]:
    result = await db.execute(
        select(InvestigationTask)
        .where(InvestigationTask.investigation_id == investigation_id)
        .order_by(InvestigationTask.created_at.desc())
    )
    return list(result.scalars().all())


async def _playbook_runs(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[PlaybookRunContext]:
    run_result = await db.execute(
        select(PlaybookRun, DefensivePlaybook)
        .join(
            DefensivePlaybook,
            PlaybookRun.playbook_id == DefensivePlaybook.id,
        )
        .where(PlaybookRun.investigation_id == investigation_id)
        .order_by(PlaybookRun.created_at.desc())
    )
    rows = list(run_result.all())
    if not rows:
        return []
    run_ids = [run.id for run, _playbook in rows]
    step_result = await db.execute(
        select(PlaybookRunStep, PlaybookStep)
        .join(PlaybookStep, PlaybookRunStep.playbook_step_id == PlaybookStep.id)
        .where(PlaybookRunStep.playbook_run_id.in_(run_ids))
        .order_by(PlaybookRunStep.playbook_run_id, PlaybookStep.order_index)
    )
    steps_by_run: dict[uuid.UUID, list[PlaybookStepContext]] = {}
    for run_step, step in step_result.all():
        steps_by_run.setdefault(run_step.playbook_run_id, []).append(
            PlaybookStepContext(
                title=step.title,
                step_type=step.step_type,
                status=run_step.status,
                analyst_note=run_step.analyst_note,
                expected_output=step.expected_output,
            )
        )
    return [
        PlaybookRunContext(
            id=run.id,
            finding_id=run.finding_id,
            playbook_name=playbook.name,
            status=run.status,
            started_at=run.started_at,
            completed_at=run.completed_at,
            completed_steps=sum(
                1
                for step in steps_by_run.get(run.id, [])
                if step.status in {"completed", "skipped"}
            ),
            total_steps=len(steps_by_run.get(run.id, [])),
            steps=steps_by_run.get(run.id, []),
        )
        for run, playbook in rows
    ]


async def _case_evidence(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[InvestigationEvidence]:
    result = await db.execute(
        select(InvestigationEvidence)
        .where(InvestigationEvidence.investigation_id == investigation_id)
        .order_by(InvestigationEvidence.created_at.desc())
    )
    return list(result.scalars().all())


async def _workflow_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[InvestigationWorkflowEvent]:
    result = await db.execute(
        select(InvestigationWorkflowEvent)
        .where(InvestigationWorkflowEvent.investigation_id == investigation_id)
        .order_by(InvestigationWorkflowEvent.created_at.desc())
    )
    return list(result.scalars().all())


async def _audit_events(
    _db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[AuditLog]:
    try:
        async with AsyncSessionLocal() as audit_db:
            result = await audit_db.execute(
                select(AuditLog)
                .where(AuditLog.investigation_id == investigation_id)
                .order_by(AuditLog.created_at.desc())
                .limit(20)
            )
            return list(result.scalars().all())
    except Exception as exc:
        logger.warning(
            "Skipping report audit summary because audit logs are unavailable: %s",
            exc,
        )
        return []


async def _finding_evidence(
    db: AsyncSession,
    finding_ids: list[uuid.UUID],
) -> list[FindingEvidence]:
    if not finding_ids:
        return []
    result = await db.execute(
        select(FindingEvidence)
        .where(FindingEvidence.finding_id.in_(finding_ids))
        .order_by(FindingEvidence.created_at)
    )
    return list(result.scalars().all())


async def _recon_entities(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[ReconEntity]:
    result = await db.execute(
        select(ReconEntity)
        .where(ReconEntity.investigation_id == investigation_id)
        .order_by(ReconEntity.entity_type, ReconEntity.value)
    )
    return list(result.scalars().all())


async def _threat_findings(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[ThreatFinding]:
    result = await db.execute(
        select(ThreatFinding)
        .where(ThreatFinding.investigation_id == investigation_id)
        .order_by(ThreatFinding.risk_score.desc(), ThreatFinding.collected_at.desc())
    )
    return list(result.scalars().all())


def _knowledge_citations(
    findings: list[Finding],
    entities: list[ReconEntity],
) -> list[KnowledgeCitation]:
    queries = [finding.title for finding in findings[:5]]
    queries.extend(entity.value for entity in entities[:5])
    queries.append("defensive report recommendations")
    citations: dict[str, KnowledgeCitation] = {}
    for query in queries:
        result = retrieve_context(query, top_k=3)
        for citation in result.citations:
            citations.setdefault(citation.id, citation)
    return list(citations.values())[:10]


def _evidence_items(findings: list[Finding]) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id=f"finding:{finding.id}",
            source_type="finding",
            title=finding.title,
            summary=finding.description,
            metadata={
                "severity": finding.severity,
                "risk_score": finding.risk_score,
                "confidence_score": finding.confidence_score,
                "source": finding.source,
            },
        )
        for finding in findings
    ]


def _knowledge_items(citations: list[KnowledgeCitation]) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id=citation.id,
            source_type="knowledge_document",
            title=citation.title,
            summary=f"{citation.framework} {citation.category}",
            metadata={
                "framework": citation.framework,
                "category": citation.category,
                "confidence_score": int(citation.confidence * 100),
            },
        )
        for citation in citations
    ]


def _risk_summary(findings: list[Finding]) -> dict[str, object]:
    highest = max((finding.risk_score for finding in findings), default=0)
    if highest >= 90:
        level = "critical"
    elif highest >= 65:
        level = "high"
    elif highest >= 35:
        level = "medium"
    elif highest > 0:
        level = "low"
    else:
        level = "not_assessed"
    return {
        "level": level,
        "highest_score": highest,
        "finding_count": len(findings),
    }


def _severity_heatmap(findings: list[Finding]) -> dict[str, int]:
    heatmap = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
    }
    for finding in findings:
        if finding.severity in heatmap:
            heatmap[finding.severity] += 1
    return heatmap


def _analysis_summary(findings: list[Finding]) -> str:
    if not findings:
        return (
            "No stored AI analysis or correlation findings are available yet. "
            "This report includes the current investigation scope and any stored "
            "entities or evidence."
        )
    high_count = sum(
        1 for finding in findings if finding.severity in ("high", "critical")
    )
    return (
        f"{len(findings)} stored findings were reviewed. "
        f"{high_count} findings are high or critical severity."
    )


def _business_impact(findings: list[Finding]) -> str:
    if not findings:
        return (
            "Business impact has not been assessed because no validated findings "
            "are currently stored for this investigation."
        )
    high_count = sum(
        1 for finding in findings if finding.severity in ("high", "critical")
    )
    if high_count:
        return (
            "High-priority findings may affect operational resilience, customer "
            "trust, or audit readiness until remediation is validated."
        )
    return (
        "Current findings indicate limited business impact, but remediation "
        "tracking should continue until all evidence is validated."
    )


def _indicator_summary(
    recon_entities: list[ReconEntity],
    threat_findings: list[ThreatFinding],
) -> list[str]:
    indicators = [
        f"{entity.entity_type}: {entity.value}"
        for entity in recon_entities[:10]
    ]
    indicators.extend(
        f"{finding.provider}: {finding.target_type} {finding.target_value} "
        f"({finding.verdict})"
        for finding in threat_findings[:10]
    )
    return indicators[:15]


def _evidence_chain(
    evidence: list[FindingEvidence],
    case_evidence: list[InvestigationEvidence],
) -> list[str]:
    chain = [
        f"{item.source} -> {item.evidence_type}: {item.description}"
        for item in evidence[:15]
    ]
    chain.extend(
        f"{item.source} -> {item.evidence_type}: {item.title}"
        for item in case_evidence[:15]
    )
    return chain[:20]


def _analyst_notes(notes: list[InvestigationNote]) -> list[str]:
    analyst_notes = [
        f"{note.note_type}: {note.title} - {note.content}" for note in notes[:10]
    ]
    analyst_notes.extend(
        [
        "Report generation used stored investigation data only.",
        "No LLM calls, live provider requests, crawling, or active scanning ran.",
        "Validate owners, scope, and remediation status before external sharing.",
        ]
    )
    return analyst_notes


def _remediation_progress(
    tasks: list[InvestigationTask],
    findings: list[Finding],
    playbook_runs: list[PlaybookRunContext],
) -> dict[str, int]:
    return {
        "total": len(tasks),
        "completed": sum(1 for task in tasks if task.status == "completed"),
        "blocked": sum(1 for task in tasks if task.status == "blocked"),
        "open": sum(
            1 for task in tasks if task.status not in {"completed", "cancelled"}
        ),
        "overdue": sum(1 for task in tasks if _task_overdue(task)),
        "validated_findings": sum(
            1 for finding in findings if finding.status == "validated"
        ),
        "unresolved_findings": sum(
            1
            for finding in findings
            if finding.status in {"new", "under_review", "accepted_risk"}
        ),
        "accepted_risk_findings": sum(
            1
            for finding in findings
            if finding.remediation_status == "accepted_risk"
        ),
        "remediated_findings": sum(
            1 for finding in findings if finding.remediation_status == "remediated"
        ),
        "playbooks_completed": sum(
            1 for run in playbook_runs if run.status == "completed"
        ),
    }


def _task_overdue(task: InvestigationTask) -> bool:
    if task.due_date is None or task.status in {"completed", "cancelled"}:
        return False
    return task.due_date < datetime.now(task.due_date.tzinfo)


def _recommendations(
    findings: list[Finding],
    citations: list[KnowledgeCitation],
) -> list[str]:
    if not findings and not citations:
        return [
            "Collect passive recon, threat intelligence, and validated findings "
            "before producing a final assessment."
        ]
    recommendations = [
        "Validate each finding with the asset owner and document remediation status.",
        "Prioritize high-risk findings with clear evidence and business impact.",
        "Preserve citations and evidence references for auditability.",
    ]
    if citations:
        recommendations.append(
            "Use mapped defensive frameworks to track mitigation ownership."
        )
    return recommendations


def _metadata(context: ReportContext) -> dict[str, Any]:
    highest_score = context.risk_summary["highest_score"]
    return {
        "report_type": context.report_type,
        "finding_count": len(context.findings),
        "recon_entity_count": len(context.recon_entities),
        "threat_finding_count": len(context.threat_findings),
        "knowledge_citation_count": len(context.knowledge_citations),
        "note_count": len(context.notes),
        "task_count": len(context.tasks),
        "case_evidence_count": len(context.case_evidence),
        "member_count": len(context.members),
        "playbook_run_count": len(context.playbook_runs),
        "bookmark_count": len(context.bookmarks),
        "tags": [tag.name for tag in context.tags],
        "priority": context.investigation.priority,
        "business_impact": context.investigation.business_impact,
        "due_date": (
            context.investigation.due_date.isoformat()
            if context.investigation.due_date
            else None
        ),
        "playbook_completed_count": sum(
            1 for run in context.playbook_runs if run.status == "completed"
        ),
        "member_roles": _member_role_counts(context.members),
        "workflow_status": context.investigation.status,
        "owner_id": str(context.investigation.owner_id),
        "reviewer_id": (
            str(context.investigation.reviewer_id)
            if context.investigation.reviewer_id
            else None
        ),
        "audit_event_count": len(context.audit_events),
        "risk_level": str(context.risk_summary["level"]),
        "highest_score": highest_score if isinstance(highest_score, int) else 0,
    }


def _member_role_counts(members: list[InvestigationMember]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for member in members:
        counts[member.role] = counts.get(member.role, 0) + 1
    return counts
