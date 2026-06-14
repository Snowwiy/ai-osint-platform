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
    "finding_reviewed",
    "ai_analysis_created",
    "report_generated",
    "report_exported",
    "knowledge_citation_observed",
    "workflow_status_changed",
    "task_created",
    "task_completed",
    "note_added",
    "note_updated",
    "note_archived",
    "bookmark_created",
    "bookmark_deleted",
    "summary_generated",
    "priority_updated",
    "tag_updated",
    "evidence_linked",
    "evidence_validated",
    "analyst_assignment",
    "member_added",
    "member_removed",
    "member_role_changed",
    "ownership_transferred",
    "task_assigned",
    "finding_assigned",
    "playbook_started",
    "playbook_step_updated",
    "playbook_completed",
    "playbook_cancelled",
    "remediation_updated",
    "finding_verified",
    "risk_accepted",
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
