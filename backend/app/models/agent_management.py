from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AgentEnrollmentToken(Base, TimestampMixin):
    __tablename__ = "agent_enrollment_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_agent_enrollment_token_hash"),
        Index("idx_agent_enrollment_token_expires", "expires_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hint: Mapped[str] = mapped_column(String(16), nullable=False)
    allowed_cidr: Mapped[str | None] = mapped_column(String(43))
    max_enrollments: Mapped[int | None] = mapped_column(Integer)
    enrollment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class AssetGroup(Base, TimestampMixin):
    __tablename__ = "asset_groups"
    __table_args__ = (UniqueConstraint("name", name="uq_asset_groups_name"),)
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class AssetGroupMembership(Base):
    __tablename__ = "asset_group_memberships"
    asset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("lan_assets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("asset_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ExpectedServiceBaseline(Base, TimestampMixin):
    __tablename__ = "expected_service_baselines"
    __table_args__ = (
        CheckConstraint(
            "(asset_id IS NULL) <> (group_id IS NULL)", name="ck_service_baseline_scope"
        ),
        Index("idx_service_baseline_asset", "asset_id"),
        Index("idx_service_baseline_group", "group_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lan_assets.id", ondelete="CASCADE")
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("asset_groups.id", ondelete="CASCADE")
    )
    expected_ports: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    allowed_ports: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
