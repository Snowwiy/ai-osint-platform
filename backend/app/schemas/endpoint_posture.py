from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

PostureStatus = Literal["healthy", "needs_review", "at_risk", "critical", "unknown"]
RecommendationSeverity = Literal["info", "low", "medium", "high", "critical"]
RecommendationStatus = Literal["open", "acknowledged", "resolved"]
EvidenceConfidence = Literal["low", "medium", "high"]


class EndpointSecurityPostureResponse(BaseModel):
    id: uuid.UUID
    lan_asset_id: uuid.UUID
    asset_ip: str
    asset_hostname: str | None
    asset_authorized: bool
    asset_criticality: str
    posture_score: int
    posture_status: PostureStatus
    firewall_status: str | None
    antivirus_status: str | None
    patch_status: str | None
    pending_reboot: bool | None
    os_name: str | None
    os_version: str | None
    disk_health: str | None
    agent_freshness: str | None
    risky_services_count: int
    recommendation_count: int
    assessed_at: datetime
    metadata: dict[str, Any]


class EndpointPostureOverviewResponse(BaseModel):
    generated_at: datetime
    total_assets: int
    assessed_assets: int
    healthy: int
    needs_review: int
    at_risk: int
    critical: int
    unknown: int
    firewall_covered: int
    antivirus_covered: int
    patch_covered: int
    unauthorized_assets: int
    open_recommendations: int
    isolation_recommendations: int
    top_actions: list[str]
    items: list[EndpointSecurityPostureResponse]
    advisory: str


class EndpointRecommendationResponse(BaseModel):
    id: uuid.UUID
    lan_asset_id: uuid.UUID
    affected_asset: str
    asset_hostname: str | None
    title: str
    severity: RecommendationSeverity
    reason: str
    recommended_action: str
    manual_steps: list[str]
    isolation_recommended: bool
    evidence_source: str
    confidence: EvidenceConfidence
    status: RecommendationStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    metadata: dict[str, Any]


class EndpointRecommendationListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[EndpointRecommendationResponse]


class EndpointRecommendationUpdate(BaseModel):
    severity: RecommendationSeverity | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_change(self) -> EndpointRecommendationUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one recommendation field is required")
        return self

    @field_validator("notes")
    @classmethod
    def safe_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        forbidden = ("password", "secret", "token", "credential", "authorization")
        if any(term in value.casefold() for term in forbidden):
            raise ValueError("notes must not contain credentials or secrets")
        return value.strip() or None


class EndpointRecommendationAction(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("notes")
    @classmethod
    def safe_notes(cls, value: str | None) -> str | None:
        return EndpointRecommendationUpdate.safe_notes(value)
