from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.finding import FindingSeverity
from app.schemas.investigation import InvestigationStage

InvestigationRiskCategory = Literal[
    "Low Risk",
    "Moderate Risk",
    "Elevated Risk",
    "High Risk",
    "Critical Risk",
]


class RiskScoreContributor(BaseModel):
    key: str
    label: str
    points: int = Field(ge=0)
    max_points: int = Field(ge=0)
    detail: str


class InvestigationRiskScoreResponse(BaseModel):
    investigation_id: uuid.UUID
    score: int = Field(ge=0, le=100)
    category: InvestigationRiskCategory
    contributors: list[RiskScoreContributor] = Field(default_factory=list)
    generated_at: datetime


class ExecutiveFinding(BaseModel):
    id: uuid.UUID
    title: str
    severity: FindingSeverity
    status: str
    risk_score: int = Field(ge=0, le=100)
    confidence_score: int = Field(ge=0, le=100)


class ExecutiveInvestigationSummaryResponse(BaseModel):
    investigation_id: uuid.UUID
    title: str
    objective: str
    authorized_scope: str
    stage: InvestigationStage
    readiness_score: int = Field(ge=0, le=100)
    readiness_category: str
    risk_score: int = Field(ge=0, le=100)
    risk_posture: InvestigationRiskCategory
    status: str
    key_findings: list[ExecutiveFinding] = Field(default_factory=list)
    unresolved_risk: str
    recurring_issues: list[str] = Field(default_factory=list)
    notable_technologies: list[str] = Field(default_factory=list)
    business_impact: str
    defensive_concerns: list[str] = Field(default_factory=list)
    remediation_urgency: str
    confidence: int = Field(ge=0, le=100)
    generated_at: datetime


class ExecutiveSignal(BaseModel):
    label: str
    count: int = Field(ge=0)


class ExecutiveAnalystWorkload(BaseModel):
    user_id: uuid.UUID
    analyst_name: str
    investigations: int = Field(ge=0)
    overdue_ownership: int = Field(ge=0)
    unresolved_findings: int = Field(ge=0)


class ExecutiveDetectionVisibility(BaseModel):
    mapped_findings: int = Field(default=0, ge=0)
    missing_coverage: int = Field(default=0, ge=0)
    coverage_percent: int = Field(default=0, ge=0, le=100)
    recurring_defensive_gaps: list[ExecutiveSignal] = Field(default_factory=list)


class ExecutiveKnowledgeUsage(BaseModel):
    most_referenced_frameworks: list[ExecutiveSignal] = Field(
        default_factory=list
    )
    common_defensive_concerns: list[ExecutiveSignal] = Field(default_factory=list)


class ExecutiveThreatIntelligence(BaseModel):
    recurring_infrastructure: int = Field(default=0, ge=0)
    recurring_indicators: int = Field(default=0, ge=0)
    active_campaigns: int = Field(default=0, ge=0)
    attack_coverage: int = Field(default=0, ge=0)
    repeated_iocs: int = Field(default=0, ge=0)
    investigations_sharing_entities: int = Field(default=0, ge=0)
    high_confidence_iocs: int = Field(default=0, ge=0)
    high_confidence_observations: int = Field(default=0, ge=0)
    unresolved_correlated_findings: int = Field(default=0, ge=0)
    recent_intelligence_activity: list[ExecutiveSignal] = Field(
        default_factory=list
    )


class ExecutiveDashboardResponse(BaseModel):
    generated_at: datetime
    active_investigations: int = Field(ge=0)
    high_risk_investigations: int = Field(ge=0)
    overdue_remediation: int = Field(ge=0)
    reporting_ready_investigations: int = Field(ge=0)
    investigations_without_remediation: int = Field(ge=0)
    investigations_missing_reports: int = Field(ge=0)
    recurring_infrastructure: list[ExecutiveSignal] = Field(default_factory=list)
    repeated_technologies: list[ExecutiveSignal] = Field(default_factory=list)
    repeated_findings: list[ExecutiveSignal] = Field(default_factory=list)
    repeated_high_risk_items: list[ExecutiveSignal] = Field(default_factory=list)
    analyst_workload: list[ExecutiveAnalystWorkload] = Field(default_factory=list)
    detection_visibility: ExecutiveDetectionVisibility = Field(
        default_factory=ExecutiveDetectionVisibility
    )
    knowledge_usage: ExecutiveKnowledgeUsage = Field(
        default_factory=ExecutiveKnowledgeUsage
    )
    threat_intelligence: ExecutiveThreatIntelligence = Field(
        default_factory=ExecutiveThreatIntelligence
    )


class ExecutivePostureFactor(BaseModel):
    key: str
    label: str
    value: int = Field(ge=0)
    detail: str


class ExecutivePostureResponse(BaseModel):
    generated_at: datetime
    score: int = Field(ge=0, le=100)
    category: Literal["Low", "Medium", "High", "Critical"]
    active_investigations: int = Field(ge=0)
    critical_findings: int = Field(ge=0)
    high_findings: int = Field(ge=0)
    open_remediation: int = Field(ge=0)
    overdue_remediation: int = Field(ge=0)
    contributing_factors: list[ExecutivePostureFactor] = Field(
        default_factory=list
    )


class ExecutiveTrendPoint(BaseModel):
    date: str
    findings: int = Field(ge=0)
    remediations_completed: int = Field(ge=0)
    investigations_created: int = Field(ge=0)
    reports_generated: int = Field(ge=0)
    risk_score: int = Field(ge=0, le=100)


class ExecutiveTrendsResponse(BaseModel):
    generated_at: datetime
    points: list[ExecutiveTrendPoint] = Field(default_factory=list)
    summary: str


class ExecutiveRecommendationItem(BaseModel):
    category: Literal["Immediate", "Short-Term", "Long-Term"]
    title: str
    recommendation: str
    evidence_refs: list[str] = Field(default_factory=list)
    related_findings: list[uuid.UUID] = Field(default_factory=list)
    related_investigations: list[uuid.UUID] = Field(default_factory=list)


class ExecutiveRecommendationsResponse(BaseModel):
    generated_at: datetime
    items: list[ExecutiveRecommendationItem] = Field(default_factory=list)
