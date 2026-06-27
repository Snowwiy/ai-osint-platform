from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EvidenceBookmark(Base):
    __tablename__ = "evidence_bookmarks"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN entity_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN finding_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN report_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_evidence_bookmarks_link",
        ),
        UniqueConstraint(
            "investigation_id",
            "entity_id",
            name="uq_evidence_bookmarks_entity",
        ),
        UniqueConstraint(
            "investigation_id",
            "finding_id",
            name="uq_evidence_bookmarks_finding",
        ),
        UniqueConstraint(
            "investigation_id",
            "report_id",
            name="uq_evidence_bookmarks_report",
        ),
        Index("idx_evidence_bookmarks_investigation", "investigation_id"),
        Index("idx_evidence_bookmarks_created_by", "created_by"),
        Index("idx_evidence_bookmarks_entity", "entity_id"),
        Index("idx_evidence_bookmarks_finding", "finding_id"),
        Index("idx_evidence_bookmarks_report", "report_id"),
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
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recon_entities.id", ondelete="CASCADE"),
        nullable=True,
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=True,
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
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
