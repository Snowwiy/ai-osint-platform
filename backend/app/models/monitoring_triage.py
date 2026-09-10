from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MonitoringAlertTriage(Base, TimestampMixin):
    __tablename__ = "monitoring_alert_triage"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'triaged', 'investigating', 'muted', 'resolved', 'false_positive')",
            name="ck_monitoring_alert_triage_status",
        ),
        CheckConstraint(
            "severity IN ('info', 'success', 'warning', 'critical')",
            name="ck_monitoring_alert_triage_severity",
        ),
        Index("idx_monitoring_triage_status", "status"),
        Index("idx_monitoring_triage_owner", "owner_id"),
        Index("idx_monitoring_triage_asset", "related_asset_id"),
        Index("idx_monitoring_triage_last_seen", text("last_seen DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"),
        unique=True, nullable=False,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="new")
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    related_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lan_assets.id", ondelete="SET NULL"), nullable=True
    )
    related_finding_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("vulnerability_baseline_findings.id", ondelete="SET NULL"), nullable=True
    )
    first_seen: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
