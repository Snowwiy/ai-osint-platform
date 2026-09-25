from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OperationalAnalysis(Base):
    __tablename__ = "operational_ai_analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'completed_with_warnings')",
            name="ck_operational_ai_analysis_status",
        ),
        CheckConstraint(
            "length(bundle_sha256) = 64",
            name="ck_operational_ai_analysis_bundle_hash",
        ),
        Index(
            "idx_operational_ai_analysis_owner_created",
            "requested_by_user_id",
            text("created_at DESC"),
        ),
        Index(
            "uq_operational_ai_analysis_dedupe_key",
            "dedupe_key",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_count: Mapped[int] = mapped_column(nullable=False, server_default="0")
    window: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    evidence_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    result: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    model_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    bundle_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
