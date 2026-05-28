from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.finding import FindingSeverity
from app.schemas.knowledge import KnowledgeSearchMode
from app.schemas.recon import JsonProperties

AnalysisMode = Literal["investigation", "ioc", "threat_context"]
AnalysisProviderStatus = Literal[
    "completed",
    "provider_unavailable",
    "provider_timeout",
    "provider_failed",
    "malformed_response",
]
IocType = Literal["ip", "domain", "url", "email", "asn"]
CitationSourceType = Literal[
    "finding",
    "finding_evidence",
    "recon_entity",
    "recon_relationship",
    "threat_finding",
    "knowledge_document",
    "framework",
    "investigation_enrichment",
]


class InvestigationAnalysisRequest(BaseModel):
    investigation_id: uuid.UUID


class IocAnalysisRequest(BaseModel):
    investigation_id: uuid.UUID
    ioc_type: IocType
    value: str = Field(min_length=1, max_length=500)

    @field_validator("value")
    @classmethod
    def strip_value(cls, value: str) -> str:
        return value.strip()


class ThreatContextAnalysisRequest(BaseModel):
    investigation_id: uuid.UUID
    finding_ids: list[uuid.UUID] = Field(default_factory=list)


class AnalysisCitation(BaseModel):
    id: str
    source_type: CitationSourceType
    title: str
    summary: str
    metadata: JsonProperties = Field(default_factory=dict)


class CitedAnalysisText(BaseModel):
    text: str
    citation_ids: list[str] = Field(default_factory=list)


class AnalysisRecommendation(BaseModel):
    action: str
    rationale: str
    citation_ids: list[str] = Field(default_factory=list)


class AnalysisFrameworkMapping(BaseModel):
    framework: str
    control: str
    rationale: str
    citation_ids: list[str] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    mode: AnalysisMode
    status: AnalysisProviderStatus
    provider: str = "anthropic"
    model: str | None = None
    investigation_id: uuid.UUID
    target_type: IocType | None = None
    target_value: str | None = None
    retrieval_mode: KnowledgeSearchMode = "hybrid"
    executive_summary: CitedAnalysisText
    technical_summary: CitedAnalysisText
    observed_indicators: list[CitedAnalysisText] = Field(default_factory=list)
    suspicious_findings: list[CitedAnalysisText] = Field(default_factory=list)
    attack_hypotheses: list[CitedAnalysisText] = Field(default_factory=list)
    severity: FindingSeverity = "info"
    confidence: int = Field(ge=0, le=100)
    recommended_next_steps: list[AnalysisRecommendation] = Field(default_factory=list)
    framework_mappings: list[AnalysisFrameworkMapping] = Field(default_factory=list)
    citations: list[AnalysisCitation] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
