from __future__ import annotations

import uuid
from datetime import datetime
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_findings_risk_score"),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_findings_confidence",
        ),
        Index("idx_findings_target_id", "target_id"),
        Index("idx_findings_source", "source"),
        Index("idx_findings_risk_score", text("risk_score DESC")),
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
    target_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    normalized_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
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
    collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
