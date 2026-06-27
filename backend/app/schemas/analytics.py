from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.case_management import InvestigationWorkflowStatus
from app.schemas.finding import FindingSeverity, FindingStatus

RiskLevel = Literal["Low", "Medium", "High", "Critical"]


class CountItem(BaseModel):
    label: str
    count: int = Field(ge=0)


class LatestActivityItem(BaseModel):
    id: str
    timestamp: datetime
    source: str
    title: str
    summary: str
    severity: FindingSeverity


class InvestigationAnalyticsItem(BaseModel):
    id: uuid.UUID
    title: str
    status: InvestigationWorkflowStatus
    created_at: datetime
    updated_at: datetime


class ReportAnalyticsItem(BaseModel):
    id: uuid.UUID
    investigation_id: uuid.UUID
    title: str | None
    report_type: str
    status: str
    created_at: datetime


class FindingAnalyticsItem(BaseModel):
    id: uuid.UUID
    investigation_id: uuid.UUID
    title: str
    severity: FindingSeverity
    status: FindingStatus
    source: str
    risk_score: int = Field(ge=0, le=100)
    confidence_score: int = Field(ge=0, le=100)
    created_at: datetime


class RiskSummary(BaseModel):
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    highest_severity: FindingSeverity | None
    highest_severity_finding: FindingAnalyticsItem | None
    high_or_critical_findings: int = Field(ge=0)
    average_finding_confidence: float = Field(ge=0, le=100)


class FindingsAnalyticsSummary(BaseModel):
    total: int = Field(ge=0)
    by_severity: dict[FindingSeverity, int]
    by_status: dict[FindingStatus, int]
    average_confidence: float = Field(ge=0, le=100)
    highest_severity_finding: FindingAnalyticsItem | None


class ReconAnalyticsSummary(BaseModel):
    total_entities: int = Field(ge=0)
    entity_counts: dict[str, int]
    relationship_count: int = Field(ge=0)
    top_external_dependencies: list[CountItem] = Field(default_factory=list)
    top_technologies: list[CountItem] = Field(default_factory=list)


class TargetAnalyticsSummary(BaseModel):
    total: int = Field(ge=0)
    by_type: dict[str, int]


class CorrelationAnalyticsSummary(BaseModel):
    total_nodes: int = Field(ge=0)
    total_edges: int = Field(ge=0)
    by_confidence: dict[str, int]


class ReportAnalyticsSummary(BaseModel):
    total: int = Field(ge=0)
    by_type: dict[str, int]
    by_status: dict[str, int]
    ready: int = Field(ge=0)
    latest_reports: list[ReportAnalyticsItem] = Field(default_factory=list)


class AiAnalysisAnalyticsSummary(BaseModel):
    total: int = Field(ge=0)
    available: bool
    latest_at: datetime | None
    by_risk: dict[str, int]


class TimelineAnalyticsSummary(BaseModel):
    total: int = Field(ge=0)
    by_event_type: dict[str, int]
    by_source: dict[str, int]


class InvestigationAnalyticsResponse(BaseModel):
    investigation_id: uuid.UUID
    generated_at: datetime
    risk_summary: RiskSummary
    findings_summary: FindingsAnalyticsSummary
    recon_summary: ReconAnalyticsSummary
    target_summary: TargetAnalyticsSummary
    correlation_summary: CorrelationAnalyticsSummary
    report_summary: ReportAnalyticsSummary
    ai_analysis_summary: AiAnalysisAnalyticsSummary
    timeline_summary: TimelineAnalyticsSummary
    top_assets: list[CountItem] = Field(default_factory=list)
    top_technologies: list[CountItem] = Field(default_factory=list)
    latest_activity: list[LatestActivityItem] = Field(default_factory=list)


class InvestigationDashboardSummary(BaseModel):
    total: int = Field(ge=0)
    active: int = Field(ge=0)
    closed: int = Field(ge=0)
    by_status: dict[InvestigationWorkflowStatus, int]


class OpenHighRiskItem(BaseModel):
    finding_id: uuid.UUID
    investigation_id: uuid.UUID
    investigation_title: str
    title: str
    severity: FindingSeverity
    risk_score: int = Field(ge=0, le=100)
    created_at: datetime


class DashboardAnalyticsResponse(BaseModel):
    generated_at: datetime
    investigation_summary: InvestigationDashboardSummary
    target_summary: TargetAnalyticsSummary
    recon_summary: ReconAnalyticsSummary
    findings_summary: FindingsAnalyticsSummary
    report_summary: ReportAnalyticsSummary
    ai_analysis_summary: AiAnalysisAnalyticsSummary
    timeline_summary: TimelineAnalyticsSummary
    latest_investigations: list[InvestigationAnalyticsItem] = Field(
        default_factory=list
    )
    latest_reports: list[ReportAnalyticsItem] = Field(default_factory=list)
    recent_activity: list[LatestActivityItem] = Field(default_factory=list)
    open_high_risk_items: list[OpenHighRiskItem] = Field(default_factory=list)


class InvestigationMetricsSummary(BaseModel):
    findings_count: int = Field(ge=0)
    validated_findings: int = Field(ge=0)
    open_tasks: int = Field(ge=0)
    overdue_tasks: int = Field(ge=0)
    average_confidence: float = Field(ge=0, le=100)
    health_score: int = Field(ge=0, le=100)
    urgent_investigations: int = Field(ge=0)
    overdue_investigations: int = Field(ge=0)


class AnalystMetricsSummary(BaseModel):
    assigned_investigations: int = Field(ge=0)
    assigned_findings: int = Field(ge=0)
    pending_reviews: int = Field(ge=0)
    completed_remediations: int = Field(ge=0)


class RiskMetricsSummary(BaseModel):
    severity_distribution: dict[FindingSeverity, int]
    confidence_average: float = Field(ge=0, le=100)
    unresolved_findings: int = Field(ge=0)


class DashboardMetricsResponse(BaseModel):
    generated_at: datetime
    investigation_metrics: InvestigationMetricsSummary
    analyst_metrics: AnalystMetricsSummary
    risk_metrics: RiskMetricsSummary
