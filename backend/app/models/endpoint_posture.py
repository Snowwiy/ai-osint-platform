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

from app.models.base import Base, TimestampMixin


class EndpointSecurityPosture(Base):
    __tablename__ = "endpoint_security_postures"
    __table_args__ = (
        UniqueConstraint("lan_asset_id", name="uq_endpoint_posture_asset"),
        CheckConstraint(
            "posture_score BETWEEN 0 AND 100", name="ck_endpoint_posture_score"
        ),
        CheckConstraint(
            "posture_status IN ('healthy', 'needs_review', 'at_risk', 'critical', 'unknown')",
            name="ck_endpoint_posture_status",
        ),
        Index("idx_endpoint_posture_status", "posture_status"),
        Index("idx_endpoint_posture_assessed", "assessed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    lan_asset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("lan_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    posture_score: Mapped[int] = mapped_column(Integer, nullable=False)
    posture_status: Mapped[str] = mapped_column(String(24), nullable=False)
    firewall_status: Mapped[str | None] = mapped_column(String(24))
    antivirus_status: Mapped[str | None] = mapped_column(String(24))
    patch_status: Mapped[str | None] = mapped_column(String(24))
    pending_reboot: Mapped[bool | None] = mapped_column(Boolean)
    os_name: Mapped[str | None] = mapped_column(String(100))
    os_version: Mapped[str | None] = mapped_column(String(100))
    disk_health: Mapped[str | None] = mapped_column(String(24))
    agent_freshness: Mapped[str | None] = mapped_column(String(24))
    risky_services_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    recommendation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    assessed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )


class EndpointRemediationRecommendation(Base, TimestampMixin):
    __tablename__ = "endpoint_remediation_recommendations"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_endpoint_recommendation_dedupe"),
        CheckConstraint(
            "severity IN ('info', 'low', 'medium', 'high', 'critical')",
            name="ck_endpoint_recommendation_severity",
        ),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_endpoint_recommendation_confidence",
        ),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')",
            name="ck_endpoint_recommendation_status",
        ),
        Index("idx_endpoint_recommendation_asset", "lan_asset_id"),
        Index("idx_endpoint_recommendation_status", "status"),
        Index("idx_endpoint_recommendation_severity", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    lan_asset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("lan_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    manual_steps: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    isolation_recommended: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    evidence_source: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", server_default="open"
    )
    notes: Mapped[str | None] = mapped_column(Text)
    acknowledged_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
