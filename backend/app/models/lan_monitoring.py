from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import DATE, JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LanAsset(Base, TimestampMixin):
    __tablename__ = "lan_assets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('online', 'offline', 'unknown')", name="ck_lan_assets_status"
        ),
        CheckConstraint(
            "confidence BETWEEN 0 AND 100", name="ck_lan_assets_confidence"
        ),
        CheckConstraint(
            "criticality IN ('low', 'medium', 'high', 'critical')",
            name="ck_lan_assets_criticality",
        ),
        UniqueConstraint("ip_address", name="uq_lan_assets_ip"),
        Index("idx_lan_assets_status", "status"),
        Index("idx_lan_assets_last_seen", "last_seen"),
        Index("idx_lan_assets_mac", "mac_address"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    mac_address: Mapped[str | None] = mapped_column(String(17), nullable=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default="unknown", server_default="unknown"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default="unknown"
    )
    source: Mapped[str] = mapped_column(
        String(40), nullable=False, default="static", server_default="static"
    )
    first_seen: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    response_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50, server_default="50"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_authorized: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    monitoring_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    criticality: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium", server_default="medium"
    )
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_function: Mapped[str | None] = mapped_column(String(255), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class LanAssetTelemetry(Base):
    __tablename__ = "lan_asset_telemetry"
    __table_args__ = (
        CheckConstraint(
            "cpu_percent IS NULL OR cpu_percent BETWEEN 0 AND 100",
            name="ck_lan_telemetry_cpu",
        ),
        CheckConstraint(
            "memory_percent IS NULL OR memory_percent BETWEEN 0 AND 100",
            name="ck_lan_telemetry_memory",
        ),
        CheckConstraint(
            "disk_percent IS NULL OR disk_percent BETWEEN 0 AND 100",
            name="ck_lan_telemetry_disk",
        ),
        Index("idx_lan_telemetry_asset_collected", "lan_asset_id", "collected_at"),
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
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    memory_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    disk_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    os_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class LanServiceObservation(Base):
    __tablename__ = "lan_service_observations"
    __table_args__ = (
        CheckConstraint("port BETWEEN 1 AND 65535", name="ck_lan_services_port"),
        CheckConstraint("protocol IN ('tcp', 'udp')", name="ck_lan_services_protocol"),
        CheckConstraint(
            "status IN ('open', 'closed', 'filtered', 'timeout', 'unknown')",
            name="ck_lan_services_status",
        ),
        CheckConstraint(
            "confidence BETWEEN 0 AND 100", name="ck_lan_services_confidence"
        ),
        Index("idx_lan_services_asset_observed", "lan_asset_id", "observed_at"),
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
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(
        String(8), nullable=False, default="tcp", server_default="tcp"
    )
    service_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    service_label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    confidence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=40, server_default="40"
    )
    banner_hint: Mapped[str | None] = mapped_column(String(160), nullable=True)
    non_standard_ssh: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", server_default="open"
    )
    observed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)


class VulnerabilityBaselineFinding(Base, TimestampMixin):
    __tablename__ = "vulnerability_baseline_findings"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'low', 'medium', 'high', 'critical')",
            name="ck_vulnerability_baseline_severity",
        ),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_vulnerability_baseline_confidence",
        ),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'in_progress', 'resolved', 'false_positive')",
            name="ck_vulnerability_baseline_status",
        ),
        UniqueConstraint("dedupe_key", name="uq_vulnerability_baseline_dedupe"),
        Index("idx_vulnerability_baseline_asset", "lan_asset_id"),
        Index("idx_vulnerability_baseline_investigation", "investigation_id"),
        Index("idx_vulnerability_baseline_severity", "severity"),
        Index("idx_vulnerability_baseline_status", "status"),
        Index("idx_vulnerability_baseline_due", "remediation_due_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    lan_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("lan_assets.id", ondelete="CASCADE"),
        nullable=True,
    )
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="SET NULL"),
        nullable=True,
    )
    rule_key: Mapped[str] = mapped_column(String(80), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium", server_default="medium"
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="open", server_default="open"
    )
    source: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="local_baseline",
        server_default="local_baseline",
    )
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    remediation_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remediation_due_date: Mapped[date | None] = mapped_column(DATE, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
