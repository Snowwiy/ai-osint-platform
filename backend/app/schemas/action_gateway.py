from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ActionOrigin = Literal[
    "manual_ui",
    "ai_recommendation",
    "analysis_workflow",
    "alert_workflow",
    "posture_workflow",
    "lan_workflow",
    "investigation_workflow",
]


class ActionProposalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1, max_length=100)
    origin: ActionOrigin = "manual_ui"
    target_id: str | None = Field(default=None, max_length=100)
    target_display_name: str | None = Field(default=None, max_length=180)
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=500)
    supporting_evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    target_snapshot: dict[str, Any] = Field(default_factory=dict)


class ActionApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_text: str | None = Field(default=None, max_length=220)
    current_snapshot: dict[str, Any] | None = None


class ActionProposalView(BaseModel):
    id: uuid.UUID
    action_id: str
    requested_by_user_id: uuid.UUID | None
    approved_by_user_id: uuid.UUID | None = None
    origin: str
    scope_type: str
    scope_id: str | None
    target_type: str
    target_id: str | None
    target_display_name: str
    target_snapshot: dict[str, Any] = Field(default_factory=dict)
    preconditions: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any]
    reason: str
    supporting_evidence_ids: list[str]
    risk_level: str
    expected_effect: str
    possible_impact: str
    rollback_guidance: str
    status: str
    expires_at: datetime
    created_at: datetime
    completed_at: datetime | None = None
    proposal_hash: str
    approval_expires_at: datetime | None = None
    result_summary: str | None = None
    safe_error_code: str | None = None
    approval_confirmation: str | None = None


class ActionProposalList(BaseModel):
    items: list[ActionProposalView]
    total: int
    enabled: bool


class ActionCapability(BaseModel):
    action_id: str
    display_name: str
    description: str
    risk_level: str
    required_role: str
    approval_required: Literal[True] = True
    executor: Literal["backend_fixed", "desktop_native"]


class ActionCapabilities(BaseModel):
    enabled: bool
    can_manage_policy: bool = False
    actions: list[ActionCapability]
    read_tools: int
    action_proposal_tools: int = Field(default=0, ge=0, le=1)
    execution_tools_exposed_to_model: Literal[0] = 0


class ActionGatewayPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class ActionGatewayPolicyView(BaseModel):
    enabled: bool
    updated_by_user_id: uuid.UUID | None = None
    updated_at: datetime | None = None


class LocalActionClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_snapshot: dict[str, Any]


class LocalActionClaimResponse(BaseModel):
    proposal_id: uuid.UUID
    action_id: str
    target_id: str
    target_display_name: str
    parameters: dict[str, Any]
    target_snapshot: dict[str, Any]
    expected_result: str


class LocalActionPreviewResponse(LocalActionClaimResponse):
    pass


class LocalActionCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    observed_state: str = Field(min_length=1, max_length=40)
    safe_error_code: str | None = Field(default=None, max_length=60)
