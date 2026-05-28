from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.investigation import Investigation
from app.models.recon_entity import ReconEntity
from app.models.report import Report
from app.models.threat_finding import ThreatFinding
from app.models.user import User
from app.schemas.report import ReportCreateRequest
from app.services.ai.evidence_builder import EvidenceItem
from app.services.ai.framework_mapper import map_frameworks
from app.services.investigation import get_investigation
from app.services.knowledge.retriever import KnowledgeCitation, retrieve_context


class ReportNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class ReportContext:
    investigation: Investigation
    report_type: str
    findings: list[Finding]
    evidence: list[FindingEvidence]
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


async def create_report(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    body: ReportCreateRequest,
) -> Report:
    investigation = await get_investigation(db, user, investigation_id)
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
        for note in context.analyst_notes:
            lines.append(f"- {note}")

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
            f"- Knowledge citations: {len(context.knowledge_citations)}",
        ]
    )
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
        recon_entities=recon_entities,
        threat_findings=threat_findings,
        knowledge_citations=knowledge_citations,
        framework_mappings=mappings,
        recommendations=_recommendations(findings, knowledge_citations),
        risk_summary=_risk_summary(findings),
        analysis_summary=_analysis_summary(findings),
        business_impact=_business_impact(findings),
        severity_heatmap=_severity_heatmap(findings),
        indicator_summary=_indicator_summary(recon_entities, threat_findings),
        evidence_chain=_evidence_chain(evidence),
        analyst_notes=_analyst_notes(),
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


def _evidence_chain(evidence: list[FindingEvidence]) -> list[str]:
    return [
        f"{item.source} -> {item.evidence_type}: {item.description}"
        for item in evidence[:15]
    ]


def _analyst_notes() -> list[str]:
    return [
        "Report generation used stored investigation data only.",
        "No LLM calls, live provider requests, crawling, or active scanning ran.",
        "Validate owners, scope, and remediation status before external sharing.",
    ]


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
        "risk_level": str(context.risk_summary["level"]),
        "highest_score": highest_score if isinstance(highest_score, int) else 0,
    }
