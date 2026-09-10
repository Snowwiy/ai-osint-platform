from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MonitoringChangeEvent(Base):
    __tablename__ = "monitoring_change_events"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'low', 'medium', 'high', 'critical')",
            name="ck_monitoring_change_severity",
        ),
        Index("idx_monitoring_changes_detected", text("detected_at DESC")),
        Index("idx_monitoring_changes_asset_detected", "asset_id", "detected_at"),
        Index("idx_monitoring_changes_type", "event_type"),
        Index("idx_monitoring_changes_acknowledged", "acknowledged_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("lan_assets.id", ondelete="CASCADE"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="info"
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )


class ServiceObservationHistory(Base):
    __tablename__ = "service_observation_history"
    __table_args__ = (
        CheckConstraint("port BETWEEN 1 AND 65535", name="ck_service_history_port"),
        CheckConstraint("protocol = 'tcp'", name="ck_service_history_protocol"),
        CheckConstraint(
            "current_status IN ('open', 'closed', 'filtered', 'timeout', 'unknown')",
            name="ck_service_history_status",
        ),
        CheckConstraint(
            "confidence BETWEEN 0 AND 100", name="ck_service_history_confidence"
        ),
        Index("idx_service_history_asset_observed", "asset_id", "observed_at"),
        Index("idx_service_history_port", "port", "protocol"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("lan_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default="tcp"
    )
    previous_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    current_status: Mapped[str] = mapped_column(String(20), nullable=False)
    service_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="40"
    )
    observed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False)
