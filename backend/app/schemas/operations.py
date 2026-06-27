from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.case_management import InvestigationWorkflowStatus
from app.schemas.finding import FindingSeverity
from app.schemas.investigation import InvestigationPriority

TriageCategory = Literal[
    "low_attention",
    "monitor",
    "active_review",
    "urgent_review",
]
RiskFilter = Literal["low", "medium", "high", "critical"]
QueueStatusFilter = Literal[
    "intake",
    "active",
    "monitoring",
    "remediation",
    "validation",
    "completed",
    "archived",
]
QueueSort = Literal[
    "newest",
    "oldest",
    "highest_risk",
    "overdue",
    "most_findings",
    "least_activity",
]
BulkAction = Literal[
    "assign_owner",
    "assign_reviewer",
    "update_priority",
    "update_tags",
    "archive",
    "change_status",
    "add_playbook",
    "generate_summary",
]


class OperationsCount(BaseModel):
    total: int = Field(ge=0)
    active: int = Field(default=0, ge=0)
    archived: int = Field(default=0, ge=0)
    urgent: int = Field(default=0, ge=0)
    overdue: int = Field(default=0, ge=0)


class FindingsOperationsSummary(BaseModel):
    total: int = Field(ge=0)
    unresolved: int = Field(ge=0)
    by_severity: dict[FindingSeverity, int]


class RemediationOperationsSummary(BaseModel):
    open_tasks: int = Field(ge=0)
    overdue_tasks: int = Field(ge=0)
    blocked_tasks: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    completion_percent: int = Field(ge=0, le=100)


class AnalystActivitySummary(BaseModel):
    recent_actions: int = Field(ge=0)
    investigations_touched: int = Field(ge=0)
    notes_created: int = Field(ge=0)
    remediation_completed: int = Field(ge=0)


class SignalCount(BaseModel):
    value: str
    count: int = Field(ge=0)
    investigation_count: int = Field(ge=0)


class InfrastructureSignalsSummary(BaseModel):
    recurring_technologies: list[SignalCount] = Field(default_factory=list)
    repeated_findings: list[SignalCount] = Field(default_factory=list)
    recurring_domains: list[SignalCount] = Field(default_factory=list)
    recurring_ips: list[SignalCount] = Field(default_factory=list)


class DashboardInvestigationItem(BaseModel):
    id: uuid.UUID
    title: str
    status: InvestigationWorkflowStatus
    priority: InvestigationPriority
    risk_score: int = Field(ge=0, le=100)
    triage_score: int = Field(ge=0, le=100)
    triage_category: TriageCategory
    findings_count: int = Field(ge=0)
    overdue_tasks: int = Field(ge=0)
    pinned: bool
    updated_at: datetime


class DashboardOverviewResponse(BaseModel):
    generated_at: datetime
    investigations: OperationsCount
    findings: FindingsOperationsSummary
    remediation: RemediationOperationsSummary
    analyst_activity: AnalystActivitySummary
    infrastructure_signals: InfrastructureSignalsSummary
    pinned_investigations: list[DashboardInvestigationItem] = Field(
        default_factory=list
    )
    recent_investigations: list[DashboardInvestigationItem] = Field(
        default_factory=list
    )


class DashboardHighlightItem(BaseModel):
    investigation_id: uuid.UUID
    title: str
    kind: Literal[
        "needs_attention",
        "overdue_remediation",
        "without_findings",
        "recently_archived",
        "recent_activity",
    ]
    detail: str
    severity: Literal["info", "low", "medium", "high", "critical"]
    occurred_at: datetime


class DashboardHighlightsResponse(BaseModel):
    generated_at: datetime
    needs_attention: list[DashboardHighlightItem] = Field(default_factory=list)
    overdue_remediation: list[DashboardHighlightItem] = Field(default_factory=list)
    without_findings: list[DashboardHighlightItem] = Field(default_factory=list)
    recently_archived: list[DashboardHighlightItem] = Field(default_factory=list)
    recent_activity: list[DashboardHighlightItem] = Field(default_factory=list)


class TriageComponents(BaseModel):
    severity: int = Field(ge=0, le=40)
    unresolved: int = Field(ge=0, le=15)
    remediation: int = Field(ge=0, le=15)
    overdue_tasks: int = Field(ge=0, le=15)
    recurring_evidence: int = Field(ge=0, le=10)
    priority: int = Field(ge=0, le=15)


class InvestigationTriageItem(BaseModel):
    investigation_id: uuid.UUID
    title: str
    score: int = Field(ge=0, le=100)
    category: TriageCategory
    components: TriageComponents
    reasons: list[str] = Field(default_factory=list)


class DashboardTriageResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[InvestigationTriageItem]


class QueueTag(BaseModel):
    id: uuid.UUID
    name: str
    color: str


class InvestigationQueueItem(BaseModel):
    id: uuid.UUID
    title: str
    status: InvestigationWorkflowStatus
    priority: InvestigationPriority
    owner_id: uuid.UUID
    reviewer_id: uuid.UUID | None
    assigned_analyst_ids: list[uuid.UUID] = Field(default_factory=list)
    due_date: date | None
    overdue: bool
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskFilter
    triage_score: int = Field(ge=0, le=100)
    triage_category: TriageCategory
    findings_count: int = Field(ge=0)
    unresolved_findings: int = Field(ge=0)
    open_tasks: int = Field(ge=0)
    overdue_tasks: int = Field(ge=0)
    tags: list[QueueTag] = Field(default_factory=list)
    pinned: bool
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime


class InvestigationQueueResponse(BaseModel):
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)
    items: list[InvestigationQueueItem]


class DashboardTimelineItem(BaseModel):
    id: int
    timestamp: datetime
    actor_id: uuid.UUID | None
    actor_name: str | None
    investigation_id: uuid.UUID | None
    investigation_title: str | None
    event_type: str
    resource_type: str | None
    resource_id: uuid.UUID | None
    metadata: dict[str, object] = Field(default_factory=dict)


class DashboardTimelineResponse(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    items: list[DashboardTimelineItem]


class AnalystWorkloadItem(BaseModel):
    user_id: uuid.UUID
    username: str
    email: str
    active_investigations: int = Field(ge=0)
    overdue_remediation: int = Field(ge=0)
    findings_assigned: int = Field(ge=0)
    notes_added_30d: int = Field(ge=0)
    remediations_completed_30d: int = Field(ge=0)
    previous_30d_completed: int = Field(ge=0)
    completion_trend: Literal["up", "steady", "down"]


class AnalystWorkloadResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[AnalystWorkloadItem]


class InvestigationPinUpdate(BaseModel):
    pinned: bool


class InvestigationPinResponse(BaseModel):
    investigation_id: uuid.UUID
    user_id: uuid.UUID
    pinned: bool


class InvestigationBulkRequest(BaseModel):
    investigation_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    action: BulkAction
    owner_id: uuid.UUID | None = None
    reviewer_id: uuid.UUID | None = None
    priority: InvestigationPriority | None = None
    tag_ids: list[uuid.UUID] | None = Field(default=None, max_length=20)
    status: InvestigationWorkflowStatus | None = None
    playbook_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> InvestigationBulkRequest:
        required_fields = {
            "assign_owner": self.owner_id,
            "assign_reviewer": self.reviewer_id,
            "update_priority": self.priority,
            "update_tags": self.tag_ids,
            "change_status": self.status,
            "add_playbook": self.playbook_id,
        }
        required = required_fields.get(self.action)
        if self.action in required_fields and required is None:
            raise ValueError(f"{self.action} requires its matching value")
        self.investigation_ids = list(dict.fromkeys(self.investigation_ids))
        return self


class InvestigationBulkResult(BaseModel):
    investigation_id: uuid.UUID
    success: bool
    detail: str


class InvestigationBulkResponse(BaseModel):
    action: BulkAction
    requested: int = Field(ge=1)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    results: list[InvestigationBulkResult]
