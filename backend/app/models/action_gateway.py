from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ActionGatewayPolicy(Base):
    __tablename__ = "action_gateway_policy"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_action_gateway_policy_singleton"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, server_default="1")
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class ActionProposal(Base):
    __tablename__ = "action_proposals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('awaiting_approval','approved','rejected','expired',"
            "'executing','completed','completed_with_warnings','failed','cancelled',"
            "'verification_failed')",
            name="ck_action_proposals_status",
        ),
        CheckConstraint(
            "risk_level IN ('low','medium','high','blocked')",
            name="ck_action_proposals_risk",
        ),
        Index("idx_action_proposals_status_created", "status", text("created_at DESC")),
        Index(
            "idx_action_proposals_requester_created",
            "requested_by_user_id",
            text("created_at DESC"),
        ),
        Index("idx_action_proposals_target", "target_type", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    action_id: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="local"
    )
    scope_id: Mapped[str | None] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(100))
    target_display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_effect: Mapped[str] = mapped_column(String(300), nullable=False)
    possible_impact: Mapped[str] = mapped_column(String(500), nullable=False)
    rollback_guidance: Mapped[str] = mapped_column(String(500), nullable=False)
    preconditions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    target_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    proposal_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="awaiting_approval"
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    result_summary: Mapped[str | None] = mapped_column(String(500))
    safe_error_code: Mapped[str | None] = mapped_column(String(60))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ActionApproval(Base):
    __tablename__ = "action_approvals"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_action_approvals_proposal"),
        Index("idx_action_approvals_expiry", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("action_proposals.id", ondelete="CASCADE"),
        nullable=False,
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    approval_method: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="human_ui"
    )
    confirmation_text: Mapped[str | None] = mapped_column(String(220))
    proposal_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    target_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class ActionTargetLock(Base):
    """Short lease preventing conflicting native actions on one local target."""

    __tablename__ = "action_target_locks"
    __table_args__ = (Index("idx_action_target_locks_expiry", "lease_expires_at"),)

    target_key: Mapped[str] = mapped_column(String(240), primary_key=True)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("action_proposals.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    lease_expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
