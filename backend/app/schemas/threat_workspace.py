from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ThreatWorkspaceConfidence = Literal["Low", "Medium", "High", "Confirmed"]


class ThreatInvestigationReference(BaseModel):
    investigation_id: uuid.UUID
    investigation_title: str
    status: str
    priority: str
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class ThreatIndicatorSummary(BaseModel):
    id: uuid.UUID
    value: str
    type: str
    source: str
    confidence: ThreatWorkspaceConfidence
    confidence_reason: str
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int = Field(ge=0)
    investigation_count: int = Field(ge=0)
    findings_count: int = Field(ge=0)
    reports_count: int = Field(ge=0)
    investigations: list[ThreatInvestigationReference] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ThreatCampaignSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    status: str
    confidence: ThreatWorkspaceConfidence
    first_observed: datetime | None = None
    last_observed: datetime | None = None
    indicator_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    investigation_count: int = Field(ge=0)
    technique_count: int = Field(ge=0)


class ThreatGroupSummary(BaseModel):
    id: uuid.UUID
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None
    confidence: ThreatWorkspaceConfidence
    notes: str | None
    campaign_count: int = Field(ge=0)
    indicator_count: int = Field(ge=0)
    technique_count: int = Field(ge=0)


class ThreatTechniqueSummary(BaseModel):
    id: str
    technique_id: str
    name: str
    tactic: str | None = None
    procedure: str | None = None
    confidence: ThreatWorkspaceConfidence
    mapped_findings: int = Field(ge=0)
    mapped_campaigns: int = Field(ge=0)
    mapped_groups: int = Field(ge=0)
    coverage_count: int = Field(ge=0)
    why_mapping_exists: str


class ThreatInfrastructureSummary(BaseModel):
    id: str
    infrastructure_type: str
    value: str
    confidence: ThreatWorkspaceConfidence
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    occurrence_count: int = Field(ge=0)
    investigation_count: int = Field(ge=0)
    investigations: list[ThreatInvestigationReference] = Field(default_factory=list)


class ThreatTimelineEvent(BaseModel):
    id: str
    timestamp: datetime
    event_type: Literal[
        "indicator_observed",
        "indicator_repeated",
        "campaign_created",
        "campaign_updated",
        "group_linked",
        "technique_mapped",
        "remediation_completed",
    ]
    title: str
    summary: str
    confidence: ThreatWorkspaceConfidence
    investigation_id: uuid.UUID | None = None
    investigation_title: str | None = None


class ThreatOverviewResponse(BaseModel):
    generated_at: datetime
    indicator_count: int = Field(ge=0)
    active_campaigns: int = Field(ge=0)
    threat_group_count: int = Field(ge=0)
    technique_count: int = Field(ge=0)
    recurring_infrastructure_count: int = Field(ge=0)
    high_confidence_observations: int = Field(ge=0)
    attack_coverage: int = Field(ge=0)
    recent_activity: list[ThreatTimelineEvent] = Field(default_factory=list)


class ThreatIndicatorListResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[ThreatIndicatorSummary] = Field(default_factory=list)


class ThreatCampaignListResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[ThreatCampaignSummary] = Field(default_factory=list)


class ThreatGroupListResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[ThreatGroupSummary] = Field(default_factory=list)


class ThreatTechniqueListResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[ThreatTechniqueSummary] = Field(default_factory=list)


class ThreatInfrastructureResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[ThreatInfrastructureSummary] = Field(default_factory=list)


class ThreatTimelineResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[ThreatTimelineEvent] = Field(default_factory=list)
