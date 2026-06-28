from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import DATE
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Engagement(Base, TimestampMixin):
    __tablename__ = "engagements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'completed', 'archived')",
            name="ck_engagements_status",
        ),
        CheckConstraint(
            "authorization_status IN ("
            "'not_provided', 'pending_review', 'approved', 'expired', 'revoked'"
            ")",
            name="ck_engagements_authorization_status",
        ),
        Index("idx_engagements_status", "status"),
        Index("idx_engagements_authorization_status", "authorization_status"),
        Index("idx_engagements_created_by", "created_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    authorization_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="not_provided",
        server_default="not_provided",
    )
    start_date: Mapped[date | None] = mapped_column(DATE, nullable=True)
    end_date: Mapped[date | None] = mapped_column(DATE, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class EngagementScopeItem(Base, TimestampMixin):
    __tablename__ = "engagement_scope_items"
    __table_args__ = (
        CheckConstraint(
            "scope_type IN ("
            "'domain', 'subdomain', 'ip', 'cidr', 'email', 'username', "
            "'organization', 'other'"
            ")",
            name="ck_engagement_scope_items_type",
        ),
        CheckConstraint(
            "status IN ('in_scope', 'out_of_scope', 'pending_review')",
            name="ck_engagement_scope_items_status",
        ),
        UniqueConstraint(
            "engagement_id",
            "scope_type",
            "value",
            name="uq_engagement_scope_item_value",
        ),
        Index("idx_engagement_scope_items_engagement", "engagement_id"),
        Index("idx_engagement_scope_items_status", "status"),
        Index("idx_engagement_scope_items_value", "value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_type: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending_review",
        server_default="pending_review",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class AuthorizationEvidence(Base, TimestampMixin):
    __tablename__ = "authorization_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ("
            "'contract', 'email_approval', 'statement_of_work', "
            "'internal_authorization', 'other'"
            ")",
            name="ck_authorization_evidence_type",
        ),
        CheckConstraint(
            "status IN ("
            "'not_provided', 'pending_review', 'approved', 'expired', 'revoked'"
            ")",
            name="ck_authorization_evidence_status",
        ),
        Index("idx_authorization_evidence_engagement", "engagement_id"),
        Index("idx_authorization_evidence_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending_review",
        server_default="pending_review",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
