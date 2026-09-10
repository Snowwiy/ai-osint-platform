from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from html import escape as escape_html
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.case_review import CaseReview
from app.models.engagement import (
    AuthorizationEvidence,
    Engagement,
    EngagementScopeItem,
)
from app.models.endpoint_posture import (
    EndpointRemediationRecommendation,
    EndpointSecurityPosture,
)
from app.models.evidence_bookmark import EvidenceBookmark
from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.investigation import Investigation
from app.models.investigation_escalation import InvestigationEscalation
from app.models.investigation_evidence import InvestigationEvidence
from app.models.investigation_handoff import InvestigationHandoff
from app.models.investigation_member import InvestigationMember
from app.models.investigation_note import InvestigationNote
from app.models.investigation_tag import InvestigationTag, InvestigationTagLink
from app.models.investigation_task import InvestigationTask
from app.models.investigation_workflow_event import InvestigationWorkflowEvent
from app.models.lan_monitoring import LanAsset
from app.models.playbook import (
    DefensivePlaybook,
    PlaybookRun,
    PlaybookRunStep,
    PlaybookStep,
)
from app.models.recon_entity import ReconEntity
from app.models.report import Report
from app.models.report_template import ReportTemplate
from app.models.threat_finding import ThreatFinding
from app.models.target import Target
from app.models.user import User
from app.schemas.ioc import (
    InvestigationPrioritizationResponse,
    IOCCorrelation,
    IOCSummary,
)
from app.schemas.report import (
    ReportCreateRequest,
    ReportQualityResponse,
    ReportQualityWarning,
)
from app.services.ai.evidence_builder import EvidenceItem
from app.services.ai.framework_mapper import map_frameworks
from app.services.case_closure import closure_report_summary
from app.services.defensive_intelligence import (
    build_coverage_response,
    build_detection_recommendations,
)
from app.services.evidence_intelligence import (
    build_investigation_evidence_intelligence_lines,
)
from app.services.executive import get_investigation_risk_score
from app.services.governance import (
    ExportControlSettings,
    ensure_export_format_allowed,
    ensure_feature_enabled,
    get_export_controls,
    get_report_branding,
)
from app.services.investigation import (
    MUTATION_ROLES,
    ensure_investigation_permission,
    get_investigation,
)
from app.services.ioc_intelligence import (
    get_investigation_prioritization,
    get_ioc_correlations,
    list_investigation_iocs,
)
from app.services.knowledge.retriever import KnowledgeCitation, retrieve_context
from app.services.operations import get_investigation_operational_snapshot
from app.services.productivity import get_investigation_readiness
from app.services.threat_workspace import (
    build_investigation_threat_intelligence_lines,
)

logger = logging.getLogger(__name__)

_ALL_REPORT_SECTIONS: list[str] = [
    "executive_summary",
    "scope",
    "authorization",
    "findings_summary",
    "severity_distribution",
    "threat_intelligence",
    "remediation_progress",
    "playbook_progress",
    "evidence_chains",
    "evidence_intelligence",
    "recurring_evidence",
    "related_investigations",
    "analyst_notes",
    "task_summary",
    "timeline_summary",
    "audit_summary",
    "framework_mapping",
    "appendix",
]
_SECTION_HEADINGS: dict[str, set[str]] = {
    "Executive Summary": {"executive_summary", "severity_distribution"},
    "Scope and Authorization": {"scope", "authorization"},
    "Methodology": {"scope", "authorization"},
    "Key Findings": {"findings_summary"},
    "Risk Summary": {"severity_distribution"},
    "Threat Intelligence": {"threat_intelligence"},
    "Technical Evidence": {
        "evidence_chains",
        "evidence_intelligence",
        "recurring_evidence",
        "related_investigations",
        "analyst_notes",
        "timeline_summary",
        "audit_summary",
    },
    "Remediation Tracking": {
        "remediation_progress",
        "playbook_progress",
        "task_summary",
    },
    "MITRE/OWASP/NIST/ISO Mapping": {"framework_mapping"},
    "Recommendations": {"executive_summary", "remediation_progress"},
    "Appendix": {"appendix"},
}
_SUBSECTION_HEADINGS: dict[str, set[str]] = {
    "Business Impact": {"executive_summary"},
    "Severity Heatmap": {"severity_distribution"},
    "Threat Intelligence": {"threat_intelligence"},
    "Threat Indicators": {"threat_intelligence"},
    "Indicators and Entities": {"evidence_chains"},
    "Evidence Chain": {"evidence_chains"},
    "Analyst Notes": {"analyst_notes"},
    "Bookmarked Evidence": {"evidence_chains"},
    "Workflow History": {"timeline_summary"},
    "Audit Summary": {"audit_summary"},
    "Case Evidence": {"evidence_chains"},
    "Evidence Intelligence": {"evidence_intelligence"},
    "Recurrence Analysis": {"evidence_intelligence"},
    "Operational Metrics": {"recurring_evidence"},
    "Operational Accountability": {"task_summary"},
    "Case Handoffs": {"timeline_summary"},
    "Recurring Infrastructure": {"recurring_evidence"},
    "Related Investigations": {"related_investigations"},
    "Task Ownership and Due Dates": {"task_summary"},
    "Defensive Playbook Progress": {"playbook_progress"},
    "Finding Verification Notes": {"remediation_progress"},
    "Analyst Summary and Recommendations": {"executive_summary"},
    "Ownership and Escalations": {"executive_summary"},
    "Collaboration Summary": {"appendix"},
    "Knowledge Citations": {"appendix"},
}


class ReportNotFoundError(Exception):
    pass


class ReportTemplateNotFoundError(Exception):
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
    engagement: Engagement | None
    engagement_scope: list[EngagementScopeItem]
    authorization_evidence: list[AuthorizationEvidence]
    report_type: str
    report_focus: str
    findings: list[Finding]
    evidence: list[FindingEvidence]
    case_evidence: list[InvestigationEvidence]
    notes: list[InvestigationNote]
    tasks: list[InvestigationTask]
    workflow_events: list[InvestigationWorkflowEvent]
    audit_events: list[AuditLog]
    members: list[InvestigationMember]
    handoffs: list[InvestigationHandoff]
    escalations: list[InvestigationEscalation]
    playbook_runs: list[PlaybookRunContext]
    bookmarks: list[EvidenceBookmark]
    tags: list[InvestigationTag]
    recon_entities: list[ReconEntity]
    threat_findings: list[ThreatFinding]
    knowledge_citations: list[KnowledgeCitation]
    framework_mappings: list[dict[str, object]]
    recommendations: list[str]
    defensive_posture: str
    detection_recommendations: list[str]
    mitre_defensive_mappings: list[dict[str, object]]
    sigma_references: list[dict[str, object]]
    monitoring_suggestions: list[str]
    prioritized_controls: list[str]
    monitoring_gaps: list[str]
    framework_references: list[str]
    iocs: list[IOCSummary]
    ioc_correlations: list[IOCCorrelation]
    ioc_prioritization: InvestigationPrioritizationResponse
    risk_summary: dict[str, object]
    analysis_summary: str
    business_impact: str
    severity_heatmap: dict[str, int]
    indicator_summary: list[str]
    threat_intelligence_summary: list[str]
    review_workflow_summary: list[str]
    closure_workflow_summary: list[str]
    evidence_chain: list[str]
    evidence_intelligence: list[str]
    analyst_notes: list[str]
    remediation_progress: dict[str, int]
    operations_summary: dict[str, object]
    recurring_infrastructure: list[str]
    related_investigations: list[str]
    enabled_sections: list[str]
    organization_name: str
    prepared_by: str
    generated_at: datetime
    confidentiality_label: str
    investigation_stage: str
    defensive_confidence: int
    investigation_risk_score: int
    investigation_risk_category: str
    readiness_score: int
    readiness_category: str
    executive_callouts: dict[str, str]


async def create_report(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    body: ReportCreateRequest,
) -> Report:
    await ensure_feature_enabled(db, "enable_report_exports")
    await ensure_export_format_allowed(db, body.output_format)
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot generate reports",
    )
    report_template = await resolve_report_template(
        db,
        report_type=body.report_type,
        template_id=body.template_id,
    )
    branding = await get_report_branding(db)
    default_title = (
        f"Informe {body.report_type.replace('_', ' ').title()} — {investigation.title}"
        if body.language == "es"
        else f"{investigation.title} {body.report_type.title()} Report"
    )
    title = body.title or " ".join(
        part for part in (branding.report_title_prefix, default_title) if part
    )
    report = Report(
        investigation_id=investigation_id,
        generated_by=user.id,
        template_id=report_template.id if report_template else None,
        title=title,
        report_type=body.report_type,
        report_format=body.output_format,
        status="queued",
        progress_label="Queued for generation",
        report_metadata={
            "template_name": report_template.name if report_template else None,
            "sections": _template_sections(report_template, body.report_type),
            "branding": branding.model_dump(),
            "language": body.language,
        },
    )
    db.add(report)
    await db.flush()
    await _generate_report_content(
        db,
        user,
        investigation,
        report,
        report_template,
    )
    return report


async def retry_report_generation(
    db: AsyncSession,
    user: User,
    report: Report,
) -> Report:
    investigation = await get_investigation(db, user, report.investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        report.investigation_id,
        MUTATION_ROLES,
        "Viewers cannot retry reports",
    )
    report_template = (
        await db.get(ReportTemplate, report.template_id)
        if report.template_id is not None
        else None
    )
    report.retry_count += 1
    report.archived_at = None
    await _generate_report_content(
        db,
        user,
        investigation,
        report,
        report_template,
    )
    return report


async def report_quality_for_investigation(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    *,
    report_type: str = "technical",
    template_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
) -> ReportQualityResponse:
    investigation = await get_investigation(db, user, investigation_id)
    report_template = await resolve_report_template(
        db,
        report_type=report_type,
        template_id=template_id,
    )
    context = await _build_context(
        db,
        user,
        investigation,
        report_type,
        enabled_sections=_template_sections(report_template, report_type),
    )
    warnings = _quality_warnings(context)
    available_evidence = _available_report_evidence(context)
    return ReportQualityResponse(
        investigation_id=investigation_id,
        report_id=report_id,
        template_id=report_template.id if report_template else None,
        warnings=warnings,
        warning_count=len(warnings),
        ready_with_warnings=bool(warnings),
        available_evidence=available_evidence,
        missing_sections=_missing_report_sections(warnings),
    )


async def resolve_report_template(
    db: AsyncSession,
    *,
    report_type: str,
    template_id: uuid.UUID | None,
) -> ReportTemplate | None:
    if template_id is not None:
        template = await db.get(ReportTemplate, template_id)
        if template is None or not template.is_active:
            raise ReportTemplateNotFoundError("Report template not found")
        if template.report_type != report_type:
            raise ReportTemplateNotFoundError(
                "Report template does not match the requested report type"
            )
        return template
    result = await db.execute(
        select(ReportTemplate)
        .where(
            ReportTemplate.report_type == report_type,
            ReportTemplate.is_active.is_(True),
            ReportTemplate.is_default.is_(True),
        )
        .order_by(ReportTemplate.created_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _generate_report_content(
    db: AsyncSession,
    user: User,
    investigation: Investigation,
    report: Report,
    report_template: ReportTemplate | None,
) -> None:
    report.status = "generating"
    report.progress_label = "Collecting stored investigation evidence"
    report.failure_reason = None
    report.error_message = None
    db.add(report)
    await db.flush()
    try:
        controls = await get_export_controls(db)
        branding = await get_report_branding(db)
        sections = _governed_sections(
            _template_sections(report_template, report.report_type),
            controls,
        )
        context = await _build_context(
            db,
            user,
            investigation,
            report.report_type,
            enabled_sections=sections,
        )
        context = _governed_context(context, controls)
        report.progress_label = "Rendering report content"
        markdown = _filter_markdown_sections(render_markdown_report(context), sections)
        html = render_html_report(context)
        language = _report_language(report.report_metadata)
        markdown, html = _localize_report_output(markdown, html, language)
        markdown, html = _apply_report_governance(
            markdown,
            html,
            context,
            controls,
            branding.model_dump(),
        )
        warnings = _quality_warnings(context)
        metadata = _metadata(context)
        metadata.update(
            {
                "template_id": (
                    str(report_template.id) if report_template is not None else None
                ),
                "template_name": (
                    report_template.name if report_template is not None else None
                ),
                "sections": sections,
                "quality_warnings": [
                    warning.model_dump() for warning in warnings
                ],
                "preferred_format": report.report_format,
                "export_controls": controls.model_dump(),
                "branding": branding.model_dump(),
                "language": language,
            }
        )
        report.html_content = html
        report.markdown_content = markdown
        report.file_size_bytes = len(html.encode("utf-8")) + len(
            markdown.encode("utf-8")
        )
        report.report_metadata = metadata
        report.status = "ready"
        report.progress_label = "Ready to download"
        report.generated_at = datetime.now(UTC)
        report.archived_at = None
    except Exception as exc:
        logger.exception("Report generation failed for report %s", report.id)
        failure_reason = _safe_failure_reason(exc)
        report.status = "failed"
        report.progress_label = "Generation failed"
        report.failure_reason = failure_reason
        report.error_message = failure_reason
        report.report_metadata = {
            **report.report_metadata,
            "generation_failed": True,
        }
    db.add(report)
    await db.flush()
    await db.refresh(report)


def _governed_sections(
    sections: list[str],
    controls: ExportControlSettings,
) -> list[str]:
    disabled: set[str] = set()
    if not controls.include_audit_summary:
        disabled.add("audit_summary")
    if not controls.include_evidence_appendix:
        disabled.update({"evidence_chains", "recurring_evidence"})
    return [section for section in sections if section not in disabled]


def _governed_context(
    context: ReportContext,
    controls: ExportControlSettings,
) -> ReportContext:
    if not controls.include_audit_summary:
        context = replace(context, audit_events=[])
    if not controls.include_evidence_appendix:
        context = replace(
            context,
            evidence=[],
            case_evidence=[],
            evidence_chain=[],
            recurring_infrastructure=[],
        )
    if controls.redact_internal_notes:
        context = replace(context, notes=[], analyst_notes=[])
    return context


def _apply_report_governance(
    markdown: str,
    html: str,
    context: ReportContext,
    controls: ExportControlSettings,
    branding: dict[str, object],
) -> tuple[str, str]:
    confidentiality = str(
        branding.get("confidentiality_label") or "Internal"
    )
    footer = str(branding.get("footer_text") or "")
    if controls.watermark_exports:
        markdown = f"> **{confidentiality}**\n\n{markdown}"
        html = html.replace(
            "<body>",
            (
                '<body><p class="meta"><strong>'
                f"{escape_html(confidentiality)}</strong></p>"
            ),
            1,
        )
    if footer:
        markdown = f"{markdown.rstrip()}\n\n---\n{footer}\n"
        html = html.replace(
            "</body>",
            f"<footer>{escape_html(footer)}</footer></body>",
            1,
        )
    if controls.redact_analyst_names:
        identifiers = {
            str(context.investigation.owner_id),
            *(
                str(member.user_id)
                for member in context.members
                if member.user_id is not None
            ),
        }
        if context.investigation.reviewer_id is not None:
            identifiers.add(str(context.investigation.reviewer_id))
        for identifier in identifiers:
            markdown = markdown.replace(identifier, "[redacted analyst]")
            html = html.replace(identifier, "[redacted analyst]")
    return markdown, html


async def list_reports(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    *,
    include_archived: bool = False,
) -> list[Report]:
    await get_investigation(db, user, investigation_id)
    statement = select(Report).where(Report.investigation_id == investigation_id)
    if not include_archived:
        statement = statement.where(Report.status != "archived")
    result = await db.execute(statement.order_by(Report.created_at.desc()))
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
    return cast(str, template.render(context=context))


def render_markdown_report(context: ReportContext) -> str:
    lines = [
        f"# {context.investigation.title} {context.report_type.title()} Report",
        "",
        f"**Organization:** {context.organization_name}",
        f"**Prepared by:** {context.prepared_by}",
        f"**Generated at:** {context.generated_at.isoformat()}",
        f"**Investigation stage:** {context.investigation_stage}",
        f"**Defensive confidence:** {context.defensive_confidence}%",
        f"**Confidentiality:** {context.confidentiality_label}",
        "",
        f"> Report focus: {context.report_focus}",
        "",
        "## Executive Summary",
        "",
        context.analysis_summary,
        "",
    ]
    if context.report_type == "executive":
        lines.extend(
            [
                "### Executive Callouts",
                "",
                f"- **Top risks:** {context.executive_callouts['top_risks']}",
                (
                    "- **Immediate remediation priorities:** "
                    f"{context.executive_callouts['remediation_priorities']}"
                ),
                (
                    "- **Investigation readiness:** "
                    f"{context.executive_callouts['readiness']}"
                ),
                (
                    "- **Key infrastructure observations:** "
                    f"{context.executive_callouts['infrastructure']}"
                ),
                "",
            ]
        )
        lines.extend(
            [
                "### Defensive Posture",
                "",
                context.defensive_posture,
                "",
                "### Monitoring Priorities",
                "",
            ]
        )
        lines.extend(
            f"- {item}" for item in context.monitoring_suggestions[:3]
        )
        lines.extend(
            [
                "",
                "### Recurring Infrastructure and Risk Indicators",
                "",
                (
                    f"- {len(context.ioc_correlations)} recurring IOC patterns "
                    "are visible across accessible investigations."
                ),
                (
                    f"- IOC prioritization: "
                    f"{context.ioc_prioritization.category} "
                    f"({context.ioc_prioritization.score}/100)."
                ),
                "",
            ]
        )
    lines.extend(
        [
        f"Workflow status: {context.investigation.status}",
        f"Investigation risk: {context.investigation_risk_category} "
        f"({context.investigation_risk_score}/100)",
        f"Case owner: {context.investigation.owner_id}",
        f"Reviewer: {context.investigation.reviewer_id or 'Unassigned'}",
        f"Members: {len(context.members)}",
        f"Assigned analysts: {_assigned_analyst_count(context.members)}",
        f"Watchers: {_watcher_count(context.members)}",
        f"Open escalations: {len(context.escalations)}",
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
        f"- Triage score: {context.operations_summary['triage_score']}/100",
        f"- Triage category: {context.operations_summary['triage_category']}",
        (
            "- Remediation completion: "
            f"{context.operations_summary['remediation_completion_percent']}%"
        ),
        "",
        "## Scope and Authorization",
        "",
        f"Engagement: {_engagement_label(context)}",
        "",
        (
            "Client: "
            f"{context.engagement.client_name if context.engagement else 'Not linked'}"
        ),
        "",
        (
            "Engagement authorization status: "
            f"{context.engagement.authorization_status if context.engagement else 'not_provided'}"
        ),
        "",
        f"Authorization: {context.investigation.authorization_statement}",
        "",
        f"Scope: {context.investigation.scope_definition or 'No scope note provided.'}",
        "",
        (
            "Investigation scope review: "
            f"{context.investigation.scope_review_status}"
        ),
        "",
        (
            "Scope notes: "
            f"{context.investigation.scope_notes or 'No scope review notes stored.'}"
        ),
        "",
        ]
    )
    lines.extend(["### Approved Engagement Scope", ""])
    if context.engagement_scope:
        for scope_item in context.engagement_scope[:20]:
            lines.append(
                f"- {scope_item.scope_type}: {scope_item.value} ({scope_item.status})"
            )
    else:
        lines.append("- No engagement scope items are stored.")
    lines.extend(["", "### Authorization Evidence Metadata", ""])
    if context.authorization_evidence:
        for evidence_item in context.authorization_evidence[:10]:
            lines.append(
                f"- {evidence_item.evidence_type}: {evidence_item.title} "
                f"({evidence_item.status})"
            )
    else:
        lines.append("- No authorization evidence metadata is stored.")
    lines.extend(
        [
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
    )
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
            "## Threat Intelligence",
            "",
        ]
    )
    if "threat_intelligence" in context.enabled_sections:
        if context.threat_intelligence_summary:
            lines.extend(
                f"- {item}" for item in context.threat_intelligence_summary
            )
        else:
            lines.append(
                "- No evidence-backed threat intelligence indicators, campaigns, "
                "or ATT&CK mappings are currently visible for this investigation."
            )
    else:
        lines.append("- Threat intelligence section is disabled for this report.")

    lines.extend(["", "## Case Review and Governance", ""])
    if context.review_workflow_summary:
        lines.extend(f"- {item}" for item in context.review_workflow_summary)
    else:
        lines.append(
            "- No formal case review workflow metadata is currently stored."
        )
    lines.extend(["", "### Case Closure and Deliverables", ""])
    if context.closure_workflow_summary:
        lines.extend(f"- {item}" for item in context.closure_workflow_summary)
    else:
        lines.append("- Case closure workflow has not been prepared.")

    lines.extend(
        [
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

    if context.report_type in {"technical", "evidence_appendix"}:
        lines.extend(["", "### IOC Intelligence", ""])
        if context.iocs:
            lines.extend(
                (
                    f"- {item.type}: {item.value} | "
                    f"confidence {item.confidence} "
                    f"({item.confidence_score}/100) | "
                    f"{item.investigation_count} accessible investigations"
                )
                for item in context.iocs
            )
        else:
            lines.append("- No reusable IOC observations are stored.")
        lines.extend(["", "### IOC Correlation Summary", ""])
        if context.ioc_correlations:
            lines.extend(
                (
                    f"- {item.ioc.value}: {item.category} across "
                    f"{item.ioc.investigation_count} investigations."
                )
                for item in context.ioc_correlations
            )
        else:
            lines.append("- No repeated IOC is visible across accessible cases.")

    if any(
        section in context.enabled_sections
        for section in (
            "evidence_chains",
            "recurring_evidence",
            "related_investigations",
            "analyst_notes",
            "timeline_summary",
            "audit_summary",
            "task_summary",
        )
    ):
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
        lines.extend(["", "### Operational Metrics", ""])
        lines.extend(
            [
                (
                    "- Assigned analysts: "
                    f"{context.operations_summary['assigned_analysts']}"
                ),
                (
                    "- Unresolved findings: "
                    f"{context.operations_summary['unresolved_findings']}"
                ),
                f"- Open tasks: {context.operations_summary['open_tasks']}",
                f"- Overdue tasks: {context.operations_summary['overdue_tasks']}",
            ]
        )
        lines.extend(["", "### Operational Accountability", ""])
        if context.tasks:
            for task in context.tasks[:10]:
                blocker = f"; blockers: {task.blockers}" if task.blockers else ""
                lines.append(
                    f"- {task.status}: {task.title}; assigned to "
                    f"{task.assigned_to or 'unassigned'}{blocker}"
                )
        else:
            lines.append("- No operational tasks are stored.")
        lines.extend(["", "### Case Handoffs", ""])
        if context.handoffs:
            for handoff in context.handoffs[:10]:
                lines.append(
                    f"- {handoff.created_at}: {handoff.previous_owner_id} -> "
                    f"{handoff.new_owner_id}; {handoff.reason}"
                )
        else:
            lines.append("- No case handoffs are stored.")
        lines.extend(["", "### Recurring Infrastructure", ""])
        if context.recurring_infrastructure:
            lines.extend(
                f"- {item}" for item in context.recurring_infrastructure
            )
        else:
            lines.append(
                "- No recurring infrastructure overlaps are visible to this user."
            )
        lines.extend(["", "### Evidence Intelligence", ""])
        if context.evidence_intelligence:
            lines.extend(f"- {item}" for item in context.evidence_intelligence)
        else:
            lines.append(
                "- No recurring evidence intelligence is visible for this "
                "investigation."
            )
        lines.extend(["", "### Related Investigations", ""])
        if context.related_investigations:
            lines.extend(f"- {item}" for item in context.related_investigations)
        else:
            lines.append(
                "- No accessible investigations share stored infrastructure."
            )

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
    lines.extend(["", "### Task Ownership and Due Dates", ""])
    if context.tasks:
        for task in context.tasks[:10]:
            due_date = task.due_date or "No due date"
            lines.append(
                f"- {task.status}: {task.title} ({task.priority}); "
                f"owner {task.assigned_to or 'unassigned'}; due {due_date}"
            )
    else:
        lines.append("- No remediation tasks are available.")
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
            if "playbook_progress" in context.enabled_sections:
                for step in playbook_run.steps:
                    note = f" - {step.analyst_note}" if step.analyst_note else ""
                    lines.append(
                        f"  - {step.status}: {step.title} "
                        f"[{step.step_type}]{note}"
                    )
    else:
        lines.append("- No defensive playbook runs are stored.")
    if "remediation_progress" in context.enabled_sections:
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
    if "executive_summary" in context.enabled_sections:
        executive_notes = [
            case_note
            for case_note in context.notes
            if case_note.note_type in {"executive", "executive_note"}
        ]
        lines.extend(["", "### Analyst Summary and Recommendations", ""])
        if executive_notes:
            for executive_note in executive_notes[:8]:
                lines.append(f"- {executive_note.title}: {executive_note.content}")
        else:
            lines.append("- No executive analyst notes are currently stored.")
        lines.extend(["", "### Ownership and Escalations", ""])
        lines.append(f"- Primary owner: {context.investigation.owner_id}")
        lines.append(
            f"- Assigned analysts: {_assigned_analyst_count(context.members)}"
        )
        lines.append(f"- Watchers: {_watcher_count(context.members)}")
        if context.escalations:
            for escalation in context.escalations[:5]:
                lines.append(
                    f"- {escalation.level.replace('_', ' ')}: "
                    f"{escalation.reason}"
                )
        else:
            lines.append("- No operational escalations are stored.")

    if context.report_type in {"technical", "compliance_mapping"}:
        lines.extend(["", "## Detection Engineering Guidance", ""])
        lines.extend(["", "### MITRE ATT&CK Defensive Mappings", ""])
        if context.mitre_defensive_mappings:
            for mapping in context.mitre_defensive_mappings:
                lines.append(
                    f"- {mapping['technique_id']} {mapping['name']} "
                    f"({mapping['tactic']}): {mapping['why_mapping_exists']}"
                )
        else:
            lines.append(
                "- No relevant ATT&CK defensive mapping was derived from evidence."
            )
        lines.extend(["", "### Sigma References", ""])
        if context.sigma_references:
            for sigma_reference in context.sigma_references:
                lines.append(
                    f"- {sigma_reference['title']} | log source "
                    f"{sigma_reference['log_source']}: "
                    f"{sigma_reference['detection_idea']}"
                )
        else:
            lines.append("- No Sigma reference matched the stored evidence.")
        lines.extend(["", "### Monitoring Suggestions", ""])
        lines.extend(
            f"- {item}" for item in context.monitoring_suggestions
        )
    if context.report_type == "remediation":
        lines.extend(["", "## Prioritized Defensive Controls", ""])
        lines.extend(
            f"- {item}" for item in context.prioritized_controls
        )
        lines.extend(["", "### Monitoring Gaps", ""])
        if context.monitoring_gaps:
            lines.extend(f"- {item}" for item in context.monitoring_gaps)
        else:
            lines.append("- No deterministic monitoring gap is currently recorded.")

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
    if context.report_type == "evidence_appendix":
        lines.extend(["", "### Defensive Framework References", ""])
        if context.framework_references:
            lines.extend(f"- {item}" for item in context.framework_references)
        else:
            lines.append("- No defensive framework references matched the evidence.")
        lines.extend(["", "### IOC Evidence References", ""])
        if context.iocs:
            lines.extend(
                (
                    f"- IOC {item.id}: {item.type} {item.value} "
                    f"({item.related_entities} linked entities, "
                    f"{item.related_findings} linked findings)"
                )
                for item in context.iocs
            )
        else:
            lines.append("- No IOC evidence references are stored.")
    return "\n".join(lines).strip() + "\n"


def _report_language(metadata: dict[str, Any] | None) -> str:
    return "es" if metadata and metadata.get("language") == "es" else "en"


def _localize_report_output(
    markdown: str, html: str, language: str
) -> tuple[str, str]:
    if language != "es":
        return (
            markdown.rstrip()
            + "\n\n## Limitations\n\nThis report is defensive and advisory. "
            "It does not validate exploitation or prove compromise.\n",
            html.replace(
                "</body>",
                "<h2>Limitations</h2><p>This report is defensive and advisory. "
                "It does not validate exploitation or prove compromise.</p></body>",
                1,
            ),
        )
    labels = {
        "Executive Summary": "Resumen ejecutivo",
        "Executive Callouts": "Puntos ejecutivos",
        "Top risks": "Riesgos principales",
        "Immediate remediation priorities": "Prioridades inmediatas de remediación",
        "Investigation readiness": "Preparación de la investigación",
        "Key infrastructure observations": "Observaciones principales de infraestructura",
        "Defensive Posture": "Postura defensiva",
        "Monitoring Priorities": "Prioridades de monitoreo",
        "Recurring Infrastructure and Risk Indicators": "Infraestructura recurrente e indicadores de riesgo",
        "Business Impact": "Impacto comercial",
        "Severity Heatmap": "Mapa de severidad",
        "Scope and Authorization": "Alcance y autorización",
        "Approved Engagement Scope": "Alcance aprobado del servicio",
        "Authorization Evidence Metadata": "Metadatos de evidencia de autorización",
        "Methodology": "Metodología",
        "Key Findings": "Hallazgos principales",
        "Risk Summary": "Resumen de riesgos",
        "Threat Intelligence": "Inteligencia de amenazas",
        "Case Review and Governance": "Revisión y gobernanza del caso",
        "Case Closure and Deliverables": "Cierre del caso y entregables",
        "Technical Evidence": "Evidencia técnica",
        "Remediation Tracking": "Seguimiento de remediación",
        "Recommendations": "Recomendaciones",
        "Appendix": "Apéndice",
        "Security Posture": "Postura de seguridad",
        "Monitoring Summary": "Resumen de monitoreo",
        "Organization": "Organización",
        "Prepared by": "Preparado por",
        "Generated at": "Generado el",
        "Investigation stage": "Etapa de investigación",
        "Defensive confidence": "Confianza defensiva",
        "Confidentiality": "Confidencialidad",
        "Report focus": "Enfoque del informe",
        "Severity": "Severidad",
        "Finding": "Hallazgo",
        "Confidence": "Confianza",
        "Evidence": "Evidencia",
        "Scope": "Alcance",
        "Source": "Fuente",
        "Status": "Estado",
        "Critical": "Crítico",
        "High": "Alto",
        "Medium": "Medio",
        "Low": "Bajo",
        "Info": "Informativo",
    }
    for english, spanish in labels.items():
        markdown = markdown.replace(f"## {english}", f"## {spanish}")
        markdown = markdown.replace(f"### {english}", f"### {spanish}")
        markdown = markdown.replace(f"**{english}:**", f"**{spanish}:**")
        html = html.replace(f">{english}<", f">{spanish}<")
        html = html.replace(f">{english}:<", f">{spanish}:<")
    html = html.replace('<html lang="en">', '<html lang="es">')
    disclaimer = "No exploit validation was performed."
    localized_disclaimer = "No se realizó validación de explotación."
    markdown = markdown.replace(disclaimer, localized_disclaimer)
    html = html.replace(disclaimer, localized_disclaimer)
    return (
        markdown.rstrip()
        + "\n\n## Limitaciones\n\nEste informe es defensivo y orientativo. "
        "No valida explotación ni demuestra compromiso.\n",
        html.replace(
            "</body>",
            "<h2>Limitaciones</h2><p>Este informe es defensivo y orientativo. "
            "No valida explotación ni demuestra compromiso.</p></body>",
            1,
        ),
    )


async def _build_context(
    db: AsyncSession,
    user: User,
    investigation: Investigation,
    report_type: str,
    *,
    enabled_sections: list[str] | None = None,
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
    reports = await _reports(db, investigation.id)
    members = await _members(db, investigation.id)
    handoffs = await _handoffs(db, investigation.id)
    escalations = await _escalations(db, investigation.id)
    playbook_runs = await _playbook_runs(db, investigation.id)
    bookmarks = await _bookmarks(db, investigation.id)
    tags = await _tags(db, investigation.id)
    engagement = await _engagement(db, investigation.engagement_id)
    engagement_scope = (
        await _engagement_scope(db, engagement.id) if engagement is not None else []
    )
    authorization_evidence = (
        await _authorization_evidence(db, engagement.id)
        if engagement is not None
        else []
    )
    branding = await get_report_branding(db)
    risk_score = await get_investigation_risk_score(
        db,
        user,
        investigation.id,
    )
    readiness = await get_investigation_readiness(
        db,
        user,
        investigation.id,
    )
    operations_summary, recurring_infrastructure = (
        await get_investigation_operational_snapshot(
            db,
            user,
            investigation.id,
        )
    )
    related_investigations = await _related_investigations(
        db,
        user,
        investigation.id,
        recon_entities,
    )
    knowledge_citations = _knowledge_citations(findings, recon_entities)
    evidence_items = _evidence_items(findings)
    knowledge_items = _knowledge_items(knowledge_citations)
    mappings = [
        mapping.model_dump()
        for mapping in map_frameworks(evidence_items, knowledge_items)
    ]
    detection_recommendations = build_detection_recommendations(
        findings,
        recon_entities,
    )
    detection_coverage = build_coverage_response(
        investigation.id,
        findings,
        detection_recommendations,
    )
    ioc_response = await list_investigation_iocs(
        db,
        user,
        investigation.id,
        limit=250,
    )
    ioc_correlations_response = await get_ioc_correlations(db, user, limit=250)
    ioc_correlations = [
        item
        for item in ioc_correlations_response.items
        if any(
            reference.investigation_id == investigation.id
            for reference in item.investigations
        )
    ]
    ioc_prioritization = await get_investigation_prioritization(
        db,
        user,
        investigation.id,
    )
    evidence_intelligence = await build_investigation_evidence_intelligence_lines(
        db,
        user,
        investigation.id,
    )
    threat_intelligence_summary = await build_investigation_threat_intelligence_lines(
        db,
        user,
        investigation.id,
    )
    review_workflow_summary = await _case_review_summary(
        db,
        investigation.id,
        findings,
        reports,
    )
    closure_workflow_summary = await closure_report_summary(db, investigation)
    defensive_confidence = (
        round(
            sum(finding.confidence_score for finding in findings)
            / len(findings)
        )
        if findings
        else 0
    )
    endpoint_posture, endpoint_recommendations = await _report_endpoint_posture(
        db, investigation.id
    )
    return ReportContext(
        investigation=investigation,
        engagement=engagement,
        engagement_scope=engagement_scope,
        authorization_evidence=authorization_evidence,
        report_type=report_type,
        report_focus=_report_focus(report_type),
        findings=findings,
        evidence=evidence,
        case_evidence=case_evidence,
        notes=notes,
        tasks=tasks,
        workflow_events=workflow_events,
        audit_events=audit_events,
        members=members,
        handoffs=handoffs,
        escalations=escalations,
        playbook_runs=playbook_runs,
        bookmarks=bookmarks,
        tags=tags,
        recon_entities=recon_entities,
        threat_findings=threat_findings,
        knowledge_citations=knowledge_citations,
        framework_mappings=mappings,
        recommendations=(
            _recommendations(findings, knowledge_citations)
            + endpoint_recommendations
        ),
        defensive_posture=(
            f"{detection_coverage.category.title()} detection visibility "
            f"({detection_coverage.coverage_percent}/100), with "
            f"{detection_coverage.mapped_findings} of "
            f"{detection_coverage.total_findings} findings mapped. "
            f"{endpoint_posture}"
        ),
        detection_recommendations=_dedupe_text(
            [
                item
                for recommendation in detection_recommendations
                for item in recommendation.monitoring_recommendations
            ]
        ),
        mitre_defensive_mappings=[
            mapping.model_dump()
            for recommendation in detection_recommendations
            for mapping in recommendation.mitre_mappings
        ],
        sigma_references=[
            reference.model_dump()
            for recommendation in detection_recommendations
            for reference in recommendation.sigma_references
        ],
        monitoring_suggestions=detection_coverage.monitoring_recommendations,
        prioritized_controls=_dedupe_text(
            [
                item
                for recommendation in detection_recommendations
                for item in recommendation.remediation_guidance
            ]
        ),
        monitoring_gaps=detection_coverage.missing_defensive_visibility,
        framework_references=_dedupe_text(
            [
                reference
                for recommendation in detection_recommendations
                for reference in recommendation.references
            ]
        ),
        iocs=ioc_response.items,
        ioc_correlations=ioc_correlations,
        ioc_prioritization=ioc_prioritization,
        risk_summary=_risk_summary(findings),
        analysis_summary=_analysis_summary(findings),
        business_impact=investigation.business_impact or _business_impact(findings),
        severity_heatmap=_severity_heatmap(findings),
        indicator_summary=_indicator_summary(recon_entities, threat_findings),
        threat_intelligence_summary=threat_intelligence_summary,
        review_workflow_summary=review_workflow_summary,
        closure_workflow_summary=closure_workflow_summary,
        evidence_chain=_evidence_chain(evidence, case_evidence),
        evidence_intelligence=evidence_intelligence,
        analyst_notes=_analyst_notes(notes),
        remediation_progress=_remediation_progress(tasks, findings, playbook_runs),
        operations_summary=operations_summary,
        recurring_infrastructure=recurring_infrastructure,
        related_investigations=related_investigations,
        enabled_sections=enabled_sections or list(_ALL_REPORT_SECTIONS),
        organization_name=branding.company_name,
        prepared_by=branding.analyst_name or user.username,
        generated_at=datetime.now(UTC),
        confidentiality_label=branding.confidentiality_label,
        investigation_stage=investigation.stage,
        defensive_confidence=defensive_confidence,
        investigation_risk_score=risk_score.score,
        investigation_risk_category=risk_score.category,
        readiness_score=readiness.score,
        readiness_category=readiness.category,
        executive_callouts=_executive_callouts(
            findings,
            tasks,
            recon_entities,
            risk_score.score,
            risk_score.category,
            readiness.score,
            readiness.category,
        ),
    )


async def _related_investigations(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    entities: list[ReconEntity],
) -> list[str]:
    values = {entity.value for entity in entities if entity.value}
    if not values:
        return []
    statement = (
        select(Investigation.id, Investigation.title, ReconEntity.value)
        .join(
            ReconEntity,
            ReconEntity.investigation_id == Investigation.id,
        )
        .where(
            Investigation.id != investigation_id,
            ReconEntity.value.in_(list(values)[:100]),
        )
    )
    if user.role != "admin":
        statement = statement.join(
            InvestigationMember,
            InvestigationMember.investigation_id == Investigation.id,
        ).where(InvestigationMember.user_id == user.id)
    result = await db.execute(statement.limit(50))
    related: dict[uuid.UUID, tuple[str, set[str]]] = {}
    for related_id, title, shared_value in result.all():
        current_title, shared_values = related.setdefault(
            related_id,
            (title, set()),
        )
        shared_values.add(shared_value)
        related[related_id] = (current_title, shared_values)
    return [
        f"{title} ({related_id}): shared {', '.join(sorted(shared_values)[:5])}"
        for related_id, (title, shared_values) in sorted(
            related.items(),
            key=lambda item: item[1][0].lower(),
        )
    ]


async def _engagement(
    db: AsyncSession,
    engagement_id: uuid.UUID | None,
) -> Engagement | None:
    if engagement_id is None:
        return None
    try:
        return await db.get(Engagement, engagement_id)
    except Exception as exc:
        logger.warning("Report engagement lookup failed: %s", exc)
        await db.rollback()
        return None


async def _engagement_scope(
    db: AsyncSession,
    engagement_id: uuid.UUID,
) -> list[EngagementScopeItem]:
    result = await db.execute(
        select(EngagementScopeItem)
        .where(EngagementScopeItem.engagement_id == engagement_id)
        .order_by(EngagementScopeItem.status, EngagementScopeItem.scope_type)
    )
    return list(result.scalars().all())


async def _authorization_evidence(
    db: AsyncSession,
    engagement_id: uuid.UUID,
) -> list[AuthorizationEvidence]:
    result = await db.execute(
        select(AuthorizationEvidence)
        .where(AuthorizationEvidence.engagement_id == engagement_id)
        .order_by(AuthorizationEvidence.status, AuthorizationEvidence.updated_at.desc())
    )
    return list(result.scalars().all())


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


async def _handoffs(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[InvestigationHandoff]:
    result = await db.execute(
        select(InvestigationHandoff)
        .where(InvestigationHandoff.investigation_id == investigation_id)
        .order_by(InvestigationHandoff.created_at.desc())
    )
    return list(result.scalars().all())


async def _escalations(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[InvestigationEscalation]:
    result = await db.execute(
        select(InvestigationEscalation)
        .where(InvestigationEscalation.investigation_id == investigation_id)
        .order_by(InvestigationEscalation.created_at.desc())
    )
    return list(result.scalars().all())


async def _tasks(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[InvestigationTask]:
    result = await db.execute(
        select(InvestigationTask)
        .where(
            InvestigationTask.investigation_id == investigation_id,
            InvestigationTask.archived_at.is_(None),
        )
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
        .where(
            PlaybookRun.investigation_id == investigation_id,
            PlaybookRun.archived_at.is_(None),
        )
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
        .where(
            InvestigationEvidence.investigation_id == investigation_id,
            InvestigationEvidence.archived_at.is_(None),
        )
        .order_by(InvestigationEvidence.created_at.desc())
    )
    return list(result.scalars().all())


async def _reports(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[Report]:
    result = await db.execute(
        select(Report).where(Report.investigation_id == investigation_id)
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


async def _case_review_summary(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    findings: list[Finding],
    reports: list[Report],
) -> list[str]:
    result = await db.execute(
        select(CaseReview).where(CaseReview.investigation_id == investigation_id)
    )
    review = result.scalar_one_or_none()
    approved_reports = sum(
        report.approval_status == "approved" for report in reports
    )
    pending_reports = sum(
        report.approval_status == "pending_approval" for report in reports
    )
    validation_counts = {
        "validated": sum(
            finding.validation_status == "validated" for finding in findings
        ),
        "pending": sum(
            finding.validation_status == "validation_pending"
            for finding in findings
        ),
        "accepted_risk": sum(
            finding.validation_status == "accepted_risk" for finding in findings
        ),
    }
    lines: list[str] = []
    if review is not None:
        lines.extend(
            [
                f"Case review status: {review.review_status}.",
                (
                    "Evidence completeness: "
                    f"{review.evidence_completeness_score}/100 "
                    f"({review.evidence_completeness_label})."
                ),
            ]
        )
        if review.closed_at:
            lines.append(
                f"Case closed at {review.closed_at.isoformat()} with preserved "
                "governance metadata."
            )
    else:
        lines.append("Case review has not been submitted.")
    lines.append(
        f"Report approvals: {approved_reports} approved, {pending_reports} pending."
    )
    lines.append(
        "Remediation validation: "
        f"{validation_counts['validated']} validated, "
        f"{validation_counts['pending']} pending, "
        f"{validation_counts['accepted_risk']} accepted risk."
    )
    return lines


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
            1 for task in tasks if task.status != "completed"
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
    if task.due_date is None or task.status == "completed":
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


async def _report_endpoint_posture(
    db: AsyncSession, investigation_id: uuid.UUID
) -> tuple[str, list[str]]:
    targets = list(
        (
            await db.execute(
                select(Target).where(Target.investigation_id == investigation_id)
            )
        )
        .scalars()
        .all()
    )
    values: set[str] = set()
    for target in targets:
        value = target.target_value.strip().casefold()
        if target.target_type == "url":
            value = (urlparse(value).hostname or "").casefold()
        if value:
            values.add(value)
    if not values:
        return (
            "No endpoint posture assessment is linked to an exact investigation target.",
            [],
        )
    rows = list(
        (
            await db.execute(
                select(EndpointSecurityPosture, LanAsset)
                .join(LanAsset, LanAsset.id == EndpointSecurityPosture.lan_asset_id)
                .where(
                    (func.lower(LanAsset.ip_address).in_(values))
                    | (func.lower(LanAsset.hostname).in_(values))
                )
            )
        ).all()
    )
    if not rows:
        return (
            "No endpoint posture assessment is linked to an exact investigation target.",
            [],
        )
    asset_ids = [posture.lan_asset_id for posture, _asset in rows]
    recommendations = list(
        (
            await db.execute(
                select(EndpointRemediationRecommendation)
                .where(
                    EndpointRemediationRecommendation.lan_asset_id.in_(asset_ids),
                    EndpointRemediationRecommendation.status.in_(
                        ("open", "acknowledged")
                    ),
                )
                .order_by(EndpointRemediationRecommendation.created_at.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    status_counts = Counter(posture.posture_status for posture, _asset in rows)
    unauthorized = sum(not asset.is_authorized for _posture, asset in rows)
    top_risks = ", ".join(item.title for item in recommendations[:3]) or "none"
    summary = (
        f"Endpoint posture (advisory): {len(rows)} matched asset(s); "
        f"{status_counts['needs_review']} need review, {status_counts['at_risk']} "
        f"at risk, {status_counts['critical']} critical, and {unauthorized} "
        f"unauthorized. Top risk indicators: {top_risks}. No exploit validation "
        "was performed."
    )
    actions = [
        f"Endpoint posture: {item.recommended_action} "
        f"({item.severity} advisory risk indicator)."
        for item in recommendations[:5]
    ]
    return summary, actions


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
        "handoff_count": len(context.handoffs),
        "escalation_count": len(context.escalations),
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
        "related_investigation_count": len(context.related_investigations),
        "recurring_evidence_count": len(context.recurring_infrastructure),
        "evidence_intelligence_count": len(context.evidence_intelligence),
        "threat_intelligence_count": len(context.threat_intelligence_summary),
        "review_workflow_count": len(context.review_workflow_summary),
        "closure_workflow_count": len(context.closure_workflow_summary),
        "closure_workflow": context.closure_workflow_summary[:10],
        "risk_level": str(context.risk_summary["level"]),
        "highest_score": highest_score if isinstance(highest_score, int) else 0,
        "investigation_risk_score": context.investigation_risk_score,
        "investigation_risk_category": context.investigation_risk_category,
        "readiness_score": context.readiness_score,
        "readiness_category": context.readiness_category,
        "prepared_by": context.prepared_by,
        "generated_at": context.generated_at.isoformat(),
        "investigation_stage": context.investigation_stage,
        "defensive_confidence": context.defensive_confidence,
        "confidentiality_label": context.confidentiality_label,
        "detection_coverage": context.defensive_posture,
        "mitre_mapping_count": len(context.mitre_defensive_mappings),
        "sigma_reference_count": len(context.sigma_references),
        "monitoring_gap_count": len(context.monitoring_gaps),
        "ioc_count": len(context.iocs),
        "recurring_ioc_count": len(context.ioc_correlations),
        "ioc_priority_score": context.ioc_prioritization.score,
        "engagement_id": str(context.engagement.id) if context.engagement else None,
        "engagement_title": context.engagement.title if context.engagement else None,
        "client_name": context.engagement.client_name if context.engagement else None,
        "authorization_status": (
            context.engagement.authorization_status
            if context.engagement
            else "not_provided"
        ),
        "scope_item_count": len(context.engagement_scope),
    }


def _engagement_label(context: ReportContext) -> str:
    if context.engagement is None:
        return "Not linked to an engagement."
    return f"{context.engagement.title} ({context.engagement.status})"


def _executive_callouts(
    findings: list[Finding],
    tasks: list[InvestigationTask],
    entities: list[ReconEntity],
    risk_score: int,
    risk_category: str,
    readiness_score: int,
    readiness_category: str,
) -> dict[str, str]:
    top_findings = sorted(
        findings,
        key=lambda finding: (finding.risk_score, finding.confidence_score),
        reverse=True,
    )[:3]
    top_risks = (
        "; ".join(finding.title for finding in top_findings)
        if top_findings
        else "No evidence-backed findings are currently stored."
    )
    overdue = [
        task
        for task in tasks
        if task.status != "completed"
        and task.due_date is not None
        and task.due_date < datetime.now(UTC)
    ]
    if overdue:
        priorities = f"Review {len(overdue)} overdue remediation tasks."
    elif tasks:
        priorities = "Maintain assigned remediation ownership and verification."
    else:
        priorities = "Assign remediation ownership for unresolved findings."
    infrastructure_values = [
        entity.value
        for entity in entities
        if entity.entity_type
        in {"Domain", "Subdomain", "IPAddress", "Service", "Technology"}
    ][:5]
    infrastructure = (
        ", ".join(infrastructure_values)
        if infrastructure_values
        else "No passive infrastructure observations are currently stored."
    )
    return {
        "top_risks": (
            f"{top_risks} Overall posture: {risk_category} ({risk_score}/100)."
        ),
        "remediation_priorities": priorities,
        "readiness": f"{readiness_category} ({readiness_score}/100).",
        "infrastructure": infrastructure,
    }


def _member_role_counts(members: list[InvestigationMember]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for member in members:
        counts[member.role] = counts.get(member.role, 0) + 1
    return counts


def _assigned_analyst_count(members: list[InvestigationMember]) -> int:
    return sum(member.role in {"admin", "analyst"} for member in members)


def _watcher_count(members: list[InvestigationMember]) -> int:
    return sum(member.role == "viewer" for member in members)


def _dedupe_text(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _template_sections(
    report_template: ReportTemplate | None,
    report_type: str,
) -> list[str]:
    if report_template is not None:
        return [
            section
            for section in report_template.sections
            if section in _ALL_REPORT_SECTIONS
        ]
    if report_type == "executive":
        return [
            "executive_summary",
            "scope",
            "authorization",
            "findings_summary",
            "severity_distribution",
            "remediation_progress",
            "framework_mapping",
            "appendix",
        ]
    return list(_ALL_REPORT_SECTIONS)


def _quality_warnings(context: ReportContext) -> list[ReportQualityWarning]:
    warnings: list[ReportQualityWarning] = []
    enabled = set(context.enabled_sections)
    if not context.findings and enabled.intersection(
        {
            "executive_summary",
            "findings_summary",
            "severity_distribution",
            "remediation_progress",
            "framework_mapping",
        }
    ):
        warnings.append(
            ReportQualityWarning(
                code="no_findings",
                message="No stored findings are available for this report.",
            )
        )
    if (
        context.report_type == "technical"
        and "analyst_notes" in enabled
        and not context.notes
    ):
        warnings.append(
            ReportQualityWarning(
                code="no_notes",
                message="No active analyst notes are stored.",
            )
        )
    if (
        context.report_type
        in {"remediation", "playbook_progress", "operational_dashboard"}
        and enabled.intersection({"remediation_progress", "task_summary"})
        and not context.tasks
    ):
        warnings.append(
            ReportQualityWarning(
                code="no_remediation_tasks",
                message="No remediation tasks are available.",
            )
        )
    if "playbook_progress" in enabled and not context.playbook_runs:
        warnings.append(
            ReportQualityWarning(
                code="no_playbook_runs",
                message="No defensive playbook runs are stored.",
            )
        )
    if "evidence_chains" in enabled and not context.evidence_chain:
        warnings.append(
            ReportQualityWarning(
                code="no_evidence_chains",
                message="No linked evidence chains are available.",
            )
        )
    if (
        "evidence_chains" in enabled
        and context.report_type == "evidence_appendix"
        and not context.bookmarks
    ):
        warnings.append(
            ReportQualityWarning(
                code="no_evidence_bookmarks",
                message="No analyst evidence bookmarks are available.",
            )
        )
    if (
        "appendix" in enabled
        and context.report_type == "evidence_appendix"
        and not context.knowledge_citations
    ):
        warnings.append(
            ReportQualityWarning(
                code="no_knowledge_citations",
                message="No local defensive knowledge citations are available.",
            )
        )
    if context.report_type == "executive" and not any(
        note.note_type in {"executive", "executive_note"} for note in context.notes
    ):
        warnings.append(
            ReportQualityWarning(
                code="no_analyst_summary",
                message="No executive analyst summary note is stored.",
            )
        )
    recent_cutoff = datetime.now(UTC) - timedelta(days=30)
    if (
        context.report_type
        in {"technical", "evidence_appendix", "operational_dashboard"}
        and enabled.intersection({"evidence_chains", "recurring_evidence"})
        and (
        not context.recon_entities
        or not any(
            entity.last_seen >= recent_cutoff for entity in context.recon_entities
        )
        )
    ):
        warnings.append(
            ReportQualityWarning(
                code="no_recent_recon",
                message="No passive recon entities were stored in the last 30 days.",
            )
        )
    if "framework_mapping" in enabled and not context.framework_mappings:
        warnings.append(
            ReportQualityWarning(
                code="no_framework_mappings",
                message="No defensive framework mappings were derived.",
            )
        )
    if (
        context.report_type
        in {"remediation", "playbook_progress", "operational_dashboard"}
        and "timeline_summary" in enabled
        and not context.workflow_events
    ):
        warnings.append(
            ReportQualityWarning(
                code="no_timeline_activity",
                message="No investigation workflow history is stored.",
            )
        )
    if context.report_type == "remediation" and context.findings:
        if not any(finding.remediation_owner for finding in context.findings):
            warnings.append(
                ReportQualityWarning(
                    code="no_remediation_owner",
                    message="No remediation owner is assigned to stored findings.",
                )
            )
        if not any(finding.verification_notes for finding in context.findings):
            warnings.append(
                ReportQualityWarning(
                    code="no_verification_notes",
                    message="No remediation verification notes are stored.",
                )
            )
    return warnings


def _available_report_evidence(context: ReportContext) -> dict[str, int]:
    return {
        "findings": len(context.findings),
        "notes": len(context.notes),
        "remediation": len(context.tasks),
        "playbooks": len(context.playbook_runs),
        "bookmarks": len(context.bookmarks),
        "knowledge_references": len(context.knowledge_citations),
        "evidence_intelligence": len(context.evidence_intelligence),
        "threat_intelligence": len(context.threat_intelligence_summary),
    }


def _missing_report_sections(
    warnings: list[ReportQualityWarning],
) -> list[str]:
    section_by_warning = {
        "no_findings": "findings",
        "no_notes": "analyst notes",
        "no_analyst_summary": "executive analyst summary",
        "no_remediation_tasks": "remediation tasks",
        "no_remediation_owner": "remediation ownership",
        "no_verification_notes": "verification notes",
        "no_playbook_runs": "playbook progress",
        "no_evidence_chains": "evidence chains",
        "no_evidence_bookmarks": "bookmarked evidence",
        "no_knowledge_citations": "knowledge references",
        "no_recent_recon": "recent passive recon",
        "no_framework_mappings": "framework mappings",
        "no_timeline_activity": "workflow history",
    }
    return list(
        dict.fromkeys(
            section_by_warning[warning.code]
            for warning in warnings
            if warning.code in section_by_warning
        )
    )


def _filter_markdown_sections(content: str, enabled_sections: list[str]) -> str:
    enabled = set(enabled_sections)
    lines = content.splitlines()
    filtered: list[str] = []
    include_section = True
    include_subsection = True
    for line in lines:
        if line.startswith("## "):
            heading = line.removeprefix("## ").strip()
            section_keys = _SECTION_HEADINGS.get(heading, {"appendix"})
            include_section = bool(enabled.intersection(section_keys))
            include_subsection = True
        elif line.startswith("### "):
            heading = line.removeprefix("### ").strip()
            subsection_keys = _SUBSECTION_HEADINGS.get(heading)
            include_subsection = (
                True
                if subsection_keys is None
                else bool(enabled.intersection(subsection_keys))
            )
        if include_section and include_subsection:
            filtered.append(line)
    return "\n".join(filtered).strip() + "\n"


def _report_focus(report_type: str) -> str:
    focuses = {
        "executive": (
            "Concise business risk, top findings, and remediation posture for "
            "decision-makers."
        ),
        "technical": (
            "Detailed entities, evidence chains, findings, defensive mappings, "
            "and citations."
        ),
        "remediation": (
            "Remediation ownership, due dates, verification notes, and unresolved "
            "risk."
        ),
        "evidence_appendix": (
            "Evidence chains, bookmarks, local citations, and traceable raw "
            "references."
        ),
        "compliance_mapping": (
            "Findings mapped to defensive frameworks and their remediation status."
        ),
        "playbook_progress": (
            "Defensive playbook runs, step completion, blockers, and analyst notes."
        ),
        "operational_dashboard": (
            "Investigation triage, workload, recurring infrastructure, and current "
            "operational posture."
        ),
    }
    return focuses.get(report_type, focuses["technical"])


def _safe_failure_reason(exc: Exception) -> str:
    if isinstance(exc, ReportTemplateNotFoundError):
        return str(exc)
    return (
        "Report generation could not complete from the currently stored "
        "investigation data."
    )
