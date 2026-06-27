from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, DATE, JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_findings_risk_score"),
        CheckConstraint(
            "confidence_score BETWEEN 0 AND 100",
            name="ck_findings_confidence_score",
        ),
        CheckConstraint(
            "severity IN ('info', 'low', 'medium', 'high', 'critical')",
            name="ck_findings_severity",
        ),
        CheckConstraint(
            "status IN ("
            "'new', 'under_review', 'validated', 'accepted_risk', "
            "'mitigated', 'false_positive', 'archived', 'open', 'resolved'"
            ")",
            name="ck_findings_status",
        ),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_findings_confidence",
        ),
        Index("idx_findings_investigation", "investigation_id"),
        Index("idx_findings_target_id", "target_id"),
        Index("idx_findings_source", "source"),
        Index("idx_findings_severity", "severity"),
        Index("idx_findings_status", "status"),
        Index("idx_findings_assigned_to", "assigned_to"),
        Index("idx_findings_reviewed_by", "reviewed_by"),
        Index("idx_findings_remediation_status", "remediation_status"),
        Index("idx_findings_remediation_owner", "remediation_owner"),
        Index("idx_findings_risk_score", text("risk_score DESC")),
        CheckConstraint(
            "remediation_status IN ("
            "'not_started', 'validating', 'remediation_planned', 'in_progress', "
            "'pending_verification', 'remediated', 'accepted_risk', "
            "'false_positive'"
            ")",
            name="ck_findings_remediation_status",
        ),
        CheckConstraint(
            "validation_status IN ("
            "'not_validated', 'validation_pending', 'validated', "
            "'validation_failed', 'accepted_risk'"
            ")",
            name="ck_findings_validation_status",
        ),
        Index("idx_findings_validation_status", "validation_status"),
        Index("idx_findings_validation_owner", "validation_owner"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    scan_job_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        nullable=True,
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="CASCADE"),
        nullable=True,
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="info",
        server_default="info",
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    normalized_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    confidence_score: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=50,
        server_default="50",
    )
    risk_score: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    confidence: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="medium",
        server_default="medium",
    )
    evidence_urls: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="new",
        server_default="new",
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="not_started",
        server_default="not_started",
    )
    remediation_owner: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    remediation_due_date: Mapped[date | None] = mapped_column(DATE, nullable=True)
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    validation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="not_validated",
        server_default="not_validated",
    )
    validation_owner: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    validation_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_history: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
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
