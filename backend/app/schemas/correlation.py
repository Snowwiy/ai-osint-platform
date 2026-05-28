from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.recon import JsonProperties

CorrelationConfidence = Literal["low", "medium", "high"]
CorrelationNodeType = Literal[
    "entity",
    "finding",
    "threat_provider",
    "knowledge_citation",
    "report",
]
CorrelationType = Literal[
    "shared_ip",
    "shared_domain",
    "shared_certificate",
    "asn_overlap",
    "provider_overlap",
    "repeated_ioc_pattern",
    "recurring_finding",
    "repeated_technology",
    "related_knowledge_citation",
]


class CorrelationNode(BaseModel):
    id: str
    node_type: CorrelationNodeType
    label: str
    source: str
    entity_id: uuid.UUID | None = None
    finding_id: uuid.UUID | None = None
    report_id: uuid.UUID | None = None
    metadata: JsonProperties = Field(default_factory=dict)


class CorrelationEdge(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    correlation_type: CorrelationType
    confidence: CorrelationConfidence
    summary: str
    evidence_count: int = Field(ge=1)
    metadata: JsonProperties = Field(default_factory=dict)


class CorrelationResponse(BaseModel):
    investigation_id: uuid.UUID
    total_nodes: int
    total_edges: int
    nodes: list[CorrelationNode] = Field(default_factory=list)
    edges: list[CorrelationEdge] = Field(default_factory=list)
