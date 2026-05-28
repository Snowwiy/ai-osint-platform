from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recon import JsonProperties

FindingSeverity = Literal["info", "low", "medium", "high", "critical"]
FindingStatus = Literal["open", "validated", "false_positive", "resolved"]
RiskBand = Literal["Low", "Medium", "High", "Critical"]


class FindingEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    finding_id: uuid.UUID
    recon_entity_id: uuid.UUID | None
    threat_finding_id: uuid.UUID | None
    evidence_type: str
    source: str
    description: str
    data: JsonProperties
    created_at: datetime


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    title: str
    description: str
    severity: FindingSeverity
    confidence_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    source: str
    status: FindingStatus
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    evidence: list[FindingEvidenceResponse] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class FindingListResponse(BaseModel):
    items: list[FindingResponse]


class FindingSummaryResponse(BaseModel):
    investigation_id: uuid.UUID
    total: int
    by_severity: dict[FindingSeverity, int]
    by_status: dict[FindingStatus, int]
    by_source: dict[str, int]
    risk_score_v2: int = Field(ge=0, le=100)
    risk_level_v2: RiskBand
    risk_signals: list[str]


class FindingStatusUpdate(BaseModel):
    status: FindingStatus
