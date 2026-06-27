from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.finding import FindingSeverity
from app.schemas.knowledge import KnowledgeFramework

CoverageLevel = Literal["weak", "partial", "moderate", "strong"]
DetectionKind = Literal["sigma", "yara"]


class MitreDefensiveMapping(BaseModel):
    technique_id: str
    name: str
    tactic: str
    defensive_explanation: str
    why_mapping_exists: str
    references: list[str] = Field(default_factory=list)


class SigmaDetectionReference(BaseModel):
    id: str
    title: str
    description: str
    log_source: str
    tags: list[str] = Field(default_factory=list)
    detection_idea: str
    defensive_explanation: str
    references: list[str] = Field(default_factory=list)


class YaraDefensiveReference(BaseModel):
    id: str
    title: str
    family: str
    category: str
    why_it_matters: str
    defensive_detection_context: str
    analyst_explanation: str
    references: list[str] = Field(default_factory=list)


class FindingDetectionRecommendation(BaseModel):
    finding_id: uuid.UUID
    finding_title: str
    severity: FindingSeverity
    why_this_matters: str
    monitoring_recommendations: list[str] = Field(default_factory=list)
    logging_recommendations: list[str] = Field(default_factory=list)
    remediation_guidance: list[str] = Field(default_factory=list)
    mitre_mappings: list[MitreDefensiveMapping] = Field(default_factory=list)
    sigma_references: list[SigmaDetectionReference] = Field(default_factory=list)
    yara_references: list[YaraDefensiveReference] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class InvestigationRecommendationsResponse(BaseModel):
    investigation_id: uuid.UUID
    generated_at: datetime
    total_findings: int = Field(ge=0)
    recommendations: list[FindingDetectionRecommendation] = Field(
        default_factory=list
    )
    recommended_next_steps: list[str] = Field(default_factory=list)


class FindingCoverageItem(BaseModel):
    finding_id: uuid.UUID
    title: str
    mapped: bool
    guidance_available: bool
    frameworks: list[str] = Field(default_factory=list)
    missing_visibility: list[str] = Field(default_factory=list)


class InvestigationCoverageResponse(BaseModel):
    investigation_id: uuid.UUID
    generated_at: datetime
    total_findings: int = Field(ge=0)
    mapped_findings: int = Field(ge=0)
    detection_guidance_available: int = Field(ge=0)
    missing_coverage: int = Field(ge=0)
    coverage_percent: int = Field(ge=0, le=100)
    category: CoverageLevel
    framework_counts: dict[str, int] = Field(default_factory=dict)
    missing_defensive_visibility: list[str] = Field(default_factory=list)
    monitoring_recommendations: list[str] = Field(default_factory=list)
    findings: list[FindingCoverageItem] = Field(default_factory=list)


class DetectionKnowledgeCard(BaseModel):
    id: str
    kind: DetectionKind
    title: str
    description: str
    category: str
    framework: KnowledgeFramework
    log_source: str | None = None
    tags: list[str] = Field(default_factory=list)
    detection_idea: str
    why_this_matters: str
    remediation_guidance: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class DetectionKnowledgeResponse(BaseModel):
    total: int = Field(ge=0)
    items: list[DetectionKnowledgeCard] = Field(default_factory=list)


class FrameworkKnowledgeCard(BaseModel):
    framework: KnowledgeFramework
    description: str
    defensive_use: str
    common_categories: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class FrameworkKnowledgeResponse(BaseModel):
    total: int = Field(ge=0)
    items: list[FrameworkKnowledgeCard] = Field(default_factory=list)
