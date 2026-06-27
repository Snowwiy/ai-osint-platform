from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.finding import FindingSeverity

IOCType = Literal[
    "ip",
    "domain",
    "subdomain",
    "url",
    "email",
    "hash",
    "asn",
    "certificate",
    "hostname",
    "technology",
]
IOCConfidence = Literal["low", "medium", "high"]
IOCPriorityCategory = Literal[
    "Low Priority",
    "Moderate Priority",
    "High Priority",
    "Immediate Review",
]
IOCCorrelationCategory = Literal[
    "recurring infrastructure",
    "recurring domains",
    "recurring IPs",
    "recurring certificates",
    "recurring technologies",
    "recurring findings",
]


class IOCInvestigationReference(BaseModel):
    investigation_id: uuid.UUID
    investigation_title: str
    first_seen: datetime
    last_seen: datetime
    recon_entity_id: uuid.UUID | None = None
    finding_count: int = Field(ge=0)


class IOCFindingReference(BaseModel):
    id: uuid.UUID
    investigation_id: uuid.UUID
    title: str
    severity: FindingSeverity
    status: str
    remediation_status: str


class IOCEvidenceRelationship(BaseModel):
    relationship_type: Literal[
        "finding",
        "report",
        "remediation",
        "timeline",
        "playbook",
        "recon_entity",
    ]
    resource_id: str
    title: str
    investigation_id: uuid.UUID
    why_this_matters: str


class IOCSummary(BaseModel):
    id: uuid.UUID
    value: str
    type: IOCType
    source: str
    confidence: IOCConfidence
    confidence_score: int = Field(ge=0, le=100)
    confidence_reason: str
    first_seen: datetime
    last_seen: datetime
    investigation_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    related_findings: int = Field(ge=0)
    related_entities: int = Field(ge=0)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class IOCDetail(IOCSummary):
    investigations: list[IOCInvestigationReference] = Field(default_factory=list)
    findings: list[IOCFindingReference] = Field(default_factory=list)
    evidence_relationships: list[IOCEvidenceRelationship] = Field(
        default_factory=list
    )
    defensive_guidance: list[str] = Field(default_factory=list)


class IOCListResponse(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    items: list[IOCSummary] = Field(default_factory=list)


class IOCCorrelation(BaseModel):
    ioc: IOCSummary
    category: IOCCorrelationCategory
    investigations: list[IOCInvestigationReference] = Field(default_factory=list)
    related_findings: list[IOCFindingReference] = Field(default_factory=list)
    severity_distribution: dict[FindingSeverity, int] = Field(default_factory=dict)


class IOCCorrelationResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[IOCCorrelation] = Field(default_factory=list)


class IOCPriorityItem(BaseModel):
    ioc: IOCSummary
    score: int = Field(ge=0, le=100)
    category: IOCPriorityCategory
    reasons: list[str] = Field(default_factory=list)


class InvestigationPrioritizationResponse(BaseModel):
    investigation_id: uuid.UUID
    generated_at: datetime
    score: int = Field(ge=0, le=100)
    category: IOCPriorityCategory
    explanation: str
    contributors: dict[str, int] = Field(default_factory=dict)
    prioritized_iocs: list[IOCPriorityItem] = Field(default_factory=list)


class IOCGuidanceCard(BaseModel):
    id: str
    title: str
    applies_to: list[str] = Field(default_factory=list)
    monitoring_guidance: list[str] = Field(default_factory=list)
    logging_recommendations: list[str] = Field(default_factory=list)
    mitre_relevance: list[str] = Field(default_factory=list)
    sigma_references: list[str] = Field(default_factory=list)
    remediation_guidance: list[str] = Field(default_factory=list)
    why_this_matters: str


class IOCGuidanceResponse(BaseModel):
    total: int = Field(ge=0)
    items: list[IOCGuidanceCard] = Field(default_factory=list)
