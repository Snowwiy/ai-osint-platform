from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

IntelligenceConfidence = Literal["Low", "Medium", "High", "Very High"]
InvestigationPrioritySuggestion = Literal["Low", "Medium", "High", "Critical"]


class IntelligenceInvestigationReference(BaseModel):
    investigation_id: uuid.UUID
    investigation_title: str
    status: str
    priority: str
    resource_id: uuid.UUID | None = None


class EvidenceIntelligenceItem(BaseModel):
    id: str
    item_type: str
    value: str
    occurrence_count: int = Field(ge=0)
    investigation_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    confidence: IntelligenceConfidence
    confidence_reasons: list[str] = Field(default_factory=list)
    related_investigations: list[IntelligenceInvestigationReference] = Field(
        default_factory=list
    )
    related_findings: list[uuid.UUID] = Field(default_factory=list)
    related_reports: list[uuid.UUID] = Field(default_factory=list)


class EvidenceIntelligenceOverviewResponse(BaseModel):
    generated_at: datetime
    total_items: int = Field(ge=0)
    recurring_domains: list[EvidenceIntelligenceItem] = Field(default_factory=list)
    recurring_ips: list[EvidenceIntelligenceItem] = Field(default_factory=list)
    recurring_technologies: list[EvidenceIntelligenceItem] = Field(default_factory=list)
    recurring_findings: list[EvidenceIntelligenceItem] = Field(default_factory=list)
    recurring_framework_mappings: list[EvidenceIntelligenceItem] = Field(
        default_factory=list
    )
    recurring_evidence_chains: list[EvidenceIntelligenceItem] = Field(
        default_factory=list
    )
    repeated_high_risk_items: list[EvidenceIntelligenceItem] = Field(
        default_factory=list
    )


class EvidenceIntelligenceEvidenceResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[EvidenceIntelligenceItem] = Field(default_factory=list)


class PriorityRecommendationItem(BaseModel):
    investigation_id: uuid.UUID
    investigation_title: str
    current_priority: str
    suggested_priority: InvestigationPrioritySuggestion
    score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    metrics: dict[str, int] = Field(default_factory=dict)


class EvidenceIntelligencePriorityResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[PriorityRecommendationItem] = Field(default_factory=list)


class EvidenceIntelligenceTimelineEvent(BaseModel):
    id: str
    timestamp: datetime
    event_type: Literal[
        "first_observed",
        "repeated_observation",
        "remediation_completed",
        "recurrence_after_remediation",
    ]
    item_type: str
    value: str
    title: str
    summary: str
    confidence: IntelligenceConfidence
    investigation_id: uuid.UUID | None = None
    investigation_title: str | None = None


class EvidenceIntelligenceTimelineResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[EvidenceIntelligenceTimelineEvent] = Field(default_factory=list)


class EvidenceIOCIntelligenceItem(BaseModel):
    ioc_id: uuid.UUID
    value: str
    type: str
    confidence: str
    investigation_count: int = Field(ge=0)
    frequency: int = Field(ge=0)
    first_seen: datetime
    last_seen: datetime
    seen_in_investigations: list[IntelligenceInvestigationReference] = Field(
        default_factory=list
    )
    seen_in_findings: list[uuid.UUID] = Field(default_factory=list)
    seen_in_reports: list[uuid.UUID] = Field(default_factory=list)


class EvidenceIntelligenceIOCResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[EvidenceIOCIntelligenceItem] = Field(default_factory=list)
