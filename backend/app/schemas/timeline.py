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
    "report_failed",
    "report_archived",
    "report_restored",
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
    "investigation_bulk_updated",
    "investigation_pinned",
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
    "ownership_changed",
    "watcher_added",
    "investigation_handoff",
    "task_status_updated",
    "investigation_escalated",
    "note_pinned",
    "investigation_state_changed",
    "investigation_stage_changed",
    "case_review_submitted",
    "case_review_approved",
    "case_review_rejected",
    "case_changes_requested",
    "case_closed",
    "case_closure_overridden",
    "report_approval_submitted",
    "report_approved",
    "report_rejected",
    "remediation_validation_submitted",
    "remediation_validated",
    "remediation_validation_failed",
    "remediation_accepted_risk",
    "closure_created",
    "closure_checklist_generated",
    "closure_checklist_item_updated",
    "closure_submitted_for_review",
    "closure_approved",
    "closure_closed",
    "closure_reopened",
    "deliverable_created",
    "deliverable_updated",
    "deliverable_approved",
    "deliverable_packaged",
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
