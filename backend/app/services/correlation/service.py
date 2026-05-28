from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.report import Report
from app.models.threat_finding import ThreatFinding
from app.models.user import User
from app.schemas.correlation import (
    CorrelationConfidence,
    CorrelationEdge,
    CorrelationNode,
    CorrelationResponse,
    CorrelationType,
)
from app.schemas.recon import JsonProperties
from app.services.investigation import get_investigation


@dataclass(frozen=True)
class CorrelationDataset:
    entities: list[ReconEntity]
    relationships: list[ReconRelationship]
    threat_findings: list[ThreatFinding]
    findings: list[Finding]
    finding_evidence: list[FindingEvidence]
    reports: list[Report]


async def get_investigation_correlations(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> CorrelationResponse:
    await get_investigation(db, user, investigation_id)
    dataset = await _load_dataset(db, investigation_id)
    builder = _CorrelationBuilder(dataset)
    response = builder.build(investigation_id)
    return response


async def _load_dataset(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> CorrelationDataset:
    entity_result = await db.execute(
        select(ReconEntity)
        .where(ReconEntity.investigation_id == investigation_id)
        .order_by(ReconEntity.entity_type, ReconEntity.value)
    )
    relationship_result = await db.execute(
        select(ReconRelationship)
        .where(ReconRelationship.investigation_id == investigation_id)
        .order_by(ReconRelationship.relationship_type, ReconRelationship.created_at)
    )
    threat_result = await db.execute(
        select(ThreatFinding)
        .where(ThreatFinding.investigation_id == investigation_id)
        .order_by(ThreatFinding.provider, ThreatFinding.target_value)
    )
    finding_result = await db.execute(
        select(Finding)
        .where(Finding.investigation_id == investigation_id)
        .order_by(Finding.source, Finding.title)
    )
    report_result = await db.execute(
        select(Report)
        .where(Report.investigation_id == investigation_id)
        .order_by(Report.created_at)
    )
    findings = list(finding_result.scalars().all())
    evidence: list[FindingEvidence] = []
    if findings:
        finding_ids = [finding.id for finding in findings]
        evidence_result = await db.execute(
            select(FindingEvidence).where(FindingEvidence.finding_id.in_(finding_ids))
        )
        evidence = list(evidence_result.scalars().all())
    return CorrelationDataset(
        entities=list(entity_result.scalars().all()),
        relationships=list(relationship_result.scalars().all()),
        threat_findings=list(threat_result.scalars().all()),
        findings=findings,
        finding_evidence=evidence,
        reports=list(report_result.scalars().all()),
    )


class _CorrelationBuilder:
    def __init__(self, dataset: CorrelationDataset) -> None:
        self.dataset = dataset
        self.nodes: dict[str, CorrelationNode] = {}
        self.edges: dict[str, CorrelationEdge] = {}
        self.entities_by_id = {entity.id: entity for entity in dataset.entities}
        self.findings_by_id = {finding.id: finding for finding in dataset.findings}

    def build(self, investigation_id: uuid.UUID) -> CorrelationResponse:
        self._detect_shared_relationship_targets("RESOLVES_TO", "shared_ip")
        self._detect_shared_relationship_targets(
            "USES_CERTIFICATE",
            "shared_certificate",
        )
        self._detect_shared_relationship_targets("BELONGS_TO", "asn_overlap")
        self._detect_shared_domains()
        self._detect_provider_overlap()
        self._detect_repeated_ioc_patterns()
        self._detect_recurring_findings()
        self._detect_repeated_technologies()
        self._detect_related_knowledge_citations()
        nodes = sorted(self.nodes.values(), key=lambda item: (item.node_type, item.id))
        edges = sorted(
            self.edges.values(),
            key=lambda item: (item.correlation_type, item.id),
        )
        return CorrelationResponse(
            investigation_id=investigation_id,
            total_nodes=len(nodes),
            total_edges=len(edges),
            nodes=nodes,
            edges=edges,
        )

    def _detect_shared_relationship_targets(
        self,
        relationship_type: str,
        correlation_type: CorrelationType,
    ) -> None:
        grouped: dict[uuid.UUID, list[ReconRelationship]] = {}
        for relationship in self.dataset.relationships:
            if relationship.relationship_type == relationship_type:
                grouped.setdefault(relationship.target_entity_id, []).append(
                    relationship
                )
        for target_id, relationships in grouped.items():
            source_ids = {item.source_entity_id for item in relationships}
            if len(source_ids) < 2:
                continue
            target = self.entities_by_id.get(target_id)
            if target is None:
                continue
            target_node = self._entity_node(target)
            confidence = _confidence_from_count(len(source_ids))
            for source_id in sorted(source_ids):
                source = self.entities_by_id.get(source_id)
                if source is None:
                    continue
                source_node = self._entity_node(source)
                self._add_edge(
                    source_node.id,
                    target_node.id,
                    correlation_type,
                    confidence,
                    f"{source.value} shares {target.value} with other entities.",
                    len(source_ids),
                    {
                        "relationship_type": relationship_type,
                        "shared_target": target.value,
                    },
                )

    def _detect_shared_domains(self) -> None:
        domains = [
            entity for entity in self.dataset.entities if entity.entity_type == "Domain"
        ]
        subdomains = [
            entity
            for entity in self.dataset.entities
            if entity.entity_type == "Subdomain"
        ]
        for domain in domains:
            matches = [
                subdomain
                for subdomain in subdomains
                if subdomain.value.endswith(f".{domain.value}")
            ]
            if len(matches) < 2:
                continue
            domain_node = self._entity_node(domain)
            confidence = _confidence_from_count(len(matches))
            for subdomain in matches:
                subdomain_node = self._entity_node(subdomain)
                self._add_edge(
                    subdomain_node.id,
                    domain_node.id,
                    "shared_domain",
                    confidence,
                    f"{subdomain.value} belongs to recurring domain {domain.value}.",
                    len(matches),
                    {"domain": domain.value},
                )

    def _detect_provider_overlap(self) -> None:
        grouped: dict[str, list[ThreatFinding]] = {}
        for threat_finding in self.dataset.threat_findings:
            grouped.setdefault(threat_finding.provider, []).append(threat_finding)
        for provider, items in grouped.items():
            if len(items) < 2:
                continue
            provider_node = self._provider_node(provider)
            confidence = _confidence_from_count(len(items))
            for item in items:
                entity = self.entities_by_id.get(item.recon_entity_id)
                if entity is None:
                    continue
                entity_node = self._entity_node(entity)
                self._add_edge(
                    entity_node.id,
                    provider_node.id,
                    "provider_overlap",
                    confidence,
                    f"{provider} produced repeated signals in this investigation.",
                    len(items),
                    {"provider": provider},
                )

    def _detect_repeated_ioc_patterns(self) -> None:
        grouped: dict[str, list[ThreatFinding]] = {}
        for threat_finding in self.dataset.threat_findings:
            key = threat_finding.target_value.lower()
            grouped.setdefault(key, []).append(threat_finding)
        for target_value, items in grouped.items():
            providers = {item.provider for item in items}
            if len(providers) < 2:
                continue
            first = items[0]
            entity = self.entities_by_id.get(first.recon_entity_id)
            if entity is None:
                continue
            entity_node = self._entity_node(entity)
            for provider in sorted(providers):
                provider_node = self._provider_node(provider)
                self._add_edge(
                    entity_node.id,
                    provider_node.id,
                    "repeated_ioc_pattern",
                    "high",
                    f"{target_value} has repeated threat provider observations.",
                    len(items),
                    {
                        "target_value": target_value,
                        "providers": sorted(providers),
                    },
                )

    def _detect_recurring_findings(self) -> None:
        grouped: dict[str, list[Finding]] = {}
        for finding in self.dataset.findings:
            key = _finding_pattern_key(finding)
            grouped.setdefault(key, []).append(finding)
        for key, findings in grouped.items():
            if len(findings) < 2:
                continue
            anchor = self._finding_node(findings[0])
            confidence = _confidence_from_count(len(findings))
            for finding in findings[1:]:
                node = self._finding_node(finding)
                self._add_edge(
                    anchor.id,
                    node.id,
                    "recurring_finding",
                    confidence,
                    f"Recurring finding pattern detected: {key}.",
                    len(findings),
                    {"pattern": key},
                )

    def _detect_repeated_technologies(self) -> None:
        grouped: dict[str, list[ReconEntity]] = {}
        for entity in self.dataset.entities:
            for technology in _technologies_from_entity(entity):
                grouped.setdefault(technology.lower(), []).append(entity)
        for technology, entities in grouped.items():
            unique = {entity.id: entity for entity in entities}
            if len(unique) < 2:
                continue
            technology_node = self._technology_node(technology)
            confidence = _confidence_from_count(len(unique))
            for entity in unique.values():
                entity_node = self._entity_node(entity)
                self._add_edge(
                    entity_node.id,
                    technology_node.id,
                    "repeated_technology",
                    confidence,
                    f"Technology '{technology}' appears across multiple entities.",
                    len(unique),
                    {"technology": technology},
                )

    def _detect_related_knowledge_citations(self) -> None:
        for report in self.dataset.reports:
            citation_ids = _knowledge_citation_ids(report)
            if not citation_ids:
                continue
            report_node = self._report_node(report)
            for citation_id in citation_ids:
                citation_node = self._knowledge_node(citation_id)
                self._add_edge(
                    report_node.id,
                    citation_node.id,
                    "related_knowledge_citation",
                    "medium",
                    "Report references local defensive knowledge.",
                    len(citation_ids),
                    {"citation_id": citation_id},
                )

    def _entity_node(self, entity: ReconEntity) -> CorrelationNode:
        node_id = f"entity:{entity.id}"
        node = self.nodes.get(node_id)
        if node is None:
            node = CorrelationNode(
                id=node_id,
                node_type="entity",
                label=f"{entity.entity_type}: {entity.value}",
                source=entity.source or "recon",
                entity_id=entity.id,
                metadata={
                    "entity_type": entity.entity_type,
                    "value": entity.value,
                },
            )
            self.nodes[node_id] = node
        return node

    def _finding_node(self, finding: Finding) -> CorrelationNode:
        node_id = f"finding:{finding.id}"
        node = self.nodes.get(node_id)
        if node is None:
            node = CorrelationNode(
                id=node_id,
                node_type="finding",
                label=finding.title,
                source=finding.source,
                finding_id=finding.id,
                metadata={
                    "severity": finding.severity,
                    "risk_score": finding.risk_score,
                },
            )
            self.nodes[node_id] = node
        return node

    def _provider_node(self, provider: str) -> CorrelationNode:
        node_id = f"provider:{provider}"
        node = self.nodes.get(node_id)
        if node is None:
            node = CorrelationNode(
                id=node_id,
                node_type="threat_provider",
                label=provider,
                source="threat_intel",
                metadata={"provider": provider},
            )
            self.nodes[node_id] = node
        return node

    def _technology_node(self, technology: str) -> CorrelationNode:
        node_id = f"technology:{_slug(technology)}"
        node = self.nodes.get(node_id)
        if node is None:
            node = CorrelationNode(
                id=node_id,
                node_type="entity",
                label=f"Technology: {technology}",
                source="recon",
                metadata={
                    "entity_type": "Technology",
                    "value": technology,
                },
            )
            self.nodes[node_id] = node
        return node

    def _report_node(self, report: Report) -> CorrelationNode:
        node_id = f"report:{report.id}"
        node = self.nodes.get(node_id)
        if node is None:
            node = CorrelationNode(
                id=node_id,
                node_type="report",
                label=report.title or "Investigation report",
                source="report",
                report_id=report.id,
                metadata={
                    "report_type": report.report_type,
                    "status": report.status,
                },
            )
            self.nodes[node_id] = node
        return node

    def _knowledge_node(self, citation_id: str) -> CorrelationNode:
        node_id = f"knowledge:{_slug(citation_id)}"
        node = self.nodes.get(node_id)
        if node is None:
            node = CorrelationNode(
                id=node_id,
                node_type="knowledge_citation",
                label=citation_id,
                source="knowledge",
                metadata={"citation_id": citation_id},
            )
            self.nodes[node_id] = node
        return node

    def _add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        correlation_type: CorrelationType,
        confidence: CorrelationConfidence,
        summary: str,
        evidence_count: int,
        metadata: JsonProperties,
    ) -> None:
        edge_id = (
            f"{correlation_type}:{_slug(source_node_id)}:"
            f"{_slug(target_node_id)}"
        )
        self.edges.setdefault(
            edge_id,
            CorrelationEdge(
                id=edge_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                correlation_type=correlation_type,
                confidence=confidence,
                summary=summary,
                evidence_count=max(1, evidence_count),
                metadata=metadata,
            ),
        )


def _confidence_from_count(count: int) -> CorrelationConfidence:
    if count >= 3:
        return "high"
    if count == 2:
        return "medium"
    return "low"


def _finding_pattern_key(finding: Finding) -> str:
    title = re.sub(r"\s+", " ", finding.title.lower()).strip()
    return f"{finding.source}:{finding.severity}:{title}"


def _technologies_from_entity(entity: ReconEntity) -> list[str]:
    values: list[str] = []
    if entity.entity_type == "Technology":
        values.append(entity.value)
    for key in ("technology", "technologies", "server", "service"):
        raw = entity.properties.get(key)
        values.extend(_strings_from_property(raw))
    return [value for value in values if value]


def _strings_from_property(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [
            item.strip()
            for item in value 
            if isinstance(item, str) and item.strip()
            ]
    return []


def _knowledge_citation_ids(report: Report) -> list[str]:
    markdown = report.markdown_content or ""
    ids = {
        item.strip("[]().,")
        for item in markdown.split()
        if item.strip("[]().,").startswith("knowledge:")
    }
    count = report.report_metadata.get("knowledge_citation_count")
    if not ids and isinstance(count, int) and count > 0:
        ids.add(f"knowledge:report:{report.id}")
    return sorted(ids)


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower() or "item"
