from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.recon import JsonProperties, TargetType

ProviderName = Literal["abuseipdb", "virustotal"]
ProviderStatus = Literal[
    "completed",
    "provider_unavailable",
    "skipped",
    "failed",
    "rate_limited",
]
ThreatIntelStatus = Literal[
    "completed",
    "partial",
    "failed",
    "provider_unavailable",
    "skipped",
]
RiskLevel = Literal["low", "medium", "high", "critical", "unknown"]
Confidence = Literal["low", "medium", "high"]


class ThreatIntelRequest(BaseModel):
    investigation_id: uuid.UUID
    target: str = Field(min_length=1, max_length=500)
    authorization_statement: str = Field(min_length=100, max_length=2000)

    @field_validator("target", "authorization_statement")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ProviderResult(BaseModel):
    provider: ProviderName
    status: ProviderStatus
    risk_score: int = Field(ge=0, le=100)
    confidence: Confidence = "low"
    verdict: str = "unknown"
    signals: list[str] = Field(default_factory=list)
    normalized: JsonProperties = Field(default_factory=dict)
    raw_data: dict[str, object] = Field(default_factory=dict)
    error_message: str | None = None


class ThreatFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    recon_entity_id: uuid.UUID
    target_type: TargetType
    target_value: str
    provider: ProviderName
    status: ProviderStatus
    risk_score: int
    confidence: Confidence
    verdict: str
    signals: list[str]
    normalized_data: JsonProperties
    error_message: str | None
    collected_at: datetime


class ThreatIntelResponse(BaseModel):
    investigation_id: uuid.UUID
    entity_id: uuid.UUID
    target_type: TargetType
    target_value: str
    status: ThreatIntelStatus
    overall_risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    provider_results: list[ProviderResult]
    findings: list[ThreatFindingResponse]
