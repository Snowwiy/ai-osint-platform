from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.finding import FindingSeverity
from app.schemas.recon import JsonProperties

TimelineEventType = Literal[
    "investigation_created",
    "recon_entity_observed",
    "recon_relationship_observed",
    "enrichment_completed",
    "threat_finding_observed",
    "finding_created",
    "ai_analysis_created",
    "report_generated",
    "knowledge_citation_observed",
]


class TimelineEvent(BaseModel):
    id: str
    timestamp: datetime
    event_type: TimelineEventType
    severity: FindingSeverity
    source: str
    title: str
    summary: str
    related_entity_ids: list[uuid.UUID] = Field(default_factory=list)
    related_finding_ids: list[uuid.UUID] = Field(default_factory=list)
    confidence: int = Field(ge=0, le=100)
    metadata: JsonProperties = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    investigation_id: uuid.UUID
    total: int
    events: list[TimelineEvent] = Field(default_factory=list)

