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


class ThreatFinding(Base):
    __tablename__ = "threat_findings"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('domain', 'ip', 'url')",
            name="ck_threat_findings_target_type",
        ),
        CheckConstraint(
            "provider IN ('abuseipdb', 'virustotal')",
            name="ck_threat_findings_provider",
        ),
        CheckConstraint(
            "status IN ("
            "'completed', 'provider_unavailable', 'skipped', "
            "'failed', 'rate_limited'"
            ")",
            name="ck_threat_findings_status",
        ),
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_threat_risk_score"),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_threat_findings_confidence",
        ),
        Index("idx_threat_findings_investigation", "investigation_id"),
        Index("idx_threat_findings_entity", "recon_entity_id"),
        Index("idx_threat_findings_provider", "provider"),
        Index("idx_threat_findings_risk_score", text("risk_score DESC")),
        Index("idx_threat_findings_collected", text("collected_at DESC")),
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
    recon_entity_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recon_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_value: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_score: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    confidence: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="low",
        server_default="low",
    )
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    signals: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    normalized_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    raw_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
