from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import DATE
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Investigation(Base, TimestampMixin):
    __tablename__ = "investigations"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'intake', 'active', 'monitoring', 'remediation', "
            "'validation', 'completed', 'archived'"
            ")",
            name="ck_investigations_status",
        ),
        CheckConstraint(
            "length(trim(authorization_statement)) >= 100",
            name="ck_investigations_auth_statement",
        ),
        Index("idx_investigations_owner", "owner_id"),
        Index("idx_investigations_reviewer", "reviewer_id"),
        Index("idx_investigations_status", "status"),
        Index("idx_investigations_priority", "priority"),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="ck_investigations_priority",
        ),
        CheckConstraint(
            "stage IN ("
            "'intake', 'scoping', 'recon', 'analysis', 'remediation', "
            "'validation', 'reporting', 'completed', 'archived'"
            ")",
            name="ck_investigations_stage",
        ),
        Index("idx_investigations_stage", "stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="intake",
        server_default="intake",
    )
    stage: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="intake",
        server_default="intake",
    )
    authorization_statement: Mapped[str] = mapped_column(Text, nullable=False)
    scope_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="medium",
        server_default="medium",
    )
    business_impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(DATE, nullable=True)
