from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CaseClosure(Base):
    __tablename__ = "case_closures"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'closed', 'reopened')",
            name="ck_case_closures_status",
        ),
        CheckConstraint(
            "final_risk_rating IN ("
            "'low', 'moderate', 'elevated', 'high', 'critical', 'not_assessed'"
            ")",
            name="ck_case_closures_final_risk_rating",
        ),
        Index("idx_case_closures_investigation", "investigation_id", unique=True),
        Index("idx_case_closures_status", "status"),
        Index("idx_case_closures_closed_at", text("closed_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    closure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_risk_rating: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="not_assessed",
        server_default="not_assessed",
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CaseClosureChecklistItem(Base):
    __tablename__ = "case_closure_checklist_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed', 'blocked', 'not_applicable')",
            name="ck_case_closure_checklist_status",
        ),
        Index(
            "idx_case_closure_checklist_investigation",
            "investigation_id",
            "key",
            unique=True,
        ),
        Index("idx_case_closure_checklist_closure", "closure_id"),
        Index("idx_case_closure_checklist_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    closure_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("case_closures.id", ondelete="CASCADE"),
        nullable=True,
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    required: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default="true",
    )
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CaseDeliverable(Base):
    __tablename__ = "case_deliverables"
    __table_args__ = (
        CheckConstraint(
            "deliverable_type IN ("
            "'executive_report', 'technical_report', 'evidence_appendix', "
            "'remediation_plan', 'scope_summary', 'audit_summary', 'final_package'"
            ")",
            name="ck_case_deliverables_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'ready', 'approved', 'delivered', 'archived')",
            name="ck_case_deliverables_status",
        ),
        CheckConstraint(
            "export_format IS NULL OR export_format IN ('pdf', 'docx', 'html', 'md')",
            name="ck_case_deliverables_export_format",
        ),
        Index("idx_case_deliverables_investigation", "investigation_id"),
        Index("idx_case_deliverables_status", "status"),
        Index("idx_case_deliverables_type", "deliverable_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    deliverable_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    export_format: Mapped[str | None] = mapped_column(String(10), nullable=True)
    file_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
