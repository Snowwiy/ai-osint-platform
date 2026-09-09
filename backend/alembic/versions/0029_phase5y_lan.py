"""Add authorized local LAN monitoring records.

Revision ID: 0029_phase5y_lan
Revises: 0028_phase5p_quality
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029_phase5y_lan"
down_revision: str | None = "0028_phase5p_quality"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lan_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("mac_address", sa.String(length=17), nullable=True),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("vendor", sa.String(length=255), nullable=True),
        sa.Column("asset_type", sa.String(length=40), server_default="unknown", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="unknown", nullable=False),
        sa.Column("source", sa.String(length=40), server_default="static", nullable=False),
        sa.Column("first_seen", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_checked_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("response_latency_ms", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Integer(), server_default="50", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_authorized", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("monitoring_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('online', 'offline', 'unknown')", name="ck_lan_assets_status"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 100", name="ck_lan_assets_confidence"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ip_address", name="uq_lan_assets_ip"),
    )
    op.create_index("idx_lan_assets_status", "lan_assets", ["status"])
    op.create_index("idx_lan_assets_last_seen", "lan_assets", ["last_seen"])
    op.create_index("idx_lan_assets_mac", "lan_assets", ["mac_address"])

    op.create_table(
        "lan_asset_telemetry",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("lan_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.Column("memory_percent", sa.Float(), nullable=True),
        sa.Column("disk_percent", sa.Float(), nullable=True),
        sa.Column("uptime_seconds", sa.Integer(), nullable=True),
        sa.Column("os_name", sa.String(length=100), nullable=True),
        sa.Column("os_version", sa.String(length=100), nullable=True),
        sa.Column("agent_version", sa.String(length=40), nullable=True),
        sa.Column("collected_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("cpu_percent IS NULL OR cpu_percent BETWEEN 0 AND 100", name="ck_lan_telemetry_cpu"),
        sa.CheckConstraint("memory_percent IS NULL OR memory_percent BETWEEN 0 AND 100", name="ck_lan_telemetry_memory"),
        sa.CheckConstraint("disk_percent IS NULL OR disk_percent BETWEEN 0 AND 100", name="ck_lan_telemetry_disk"),
        sa.ForeignKeyConstraint(["lan_asset_id"], ["lan_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_lan_telemetry_asset_collected", "lan_asset_telemetry", ["lan_asset_id", "collected_at"])

    op.create_table(
        "lan_service_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("lan_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=8), server_default="tcp", nullable=False),
        sa.Column("service_name", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("observed_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.CheckConstraint("port BETWEEN 1 AND 65535", name="ck_lan_services_port"),
        sa.CheckConstraint("protocol IN ('tcp', 'udp')", name="ck_lan_services_protocol"),
        sa.CheckConstraint("status IN ('open', 'closed', 'unknown')", name="ck_lan_services_status"),
        sa.ForeignKeyConstraint(["lan_asset_id"], ["lan_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_lan_services_asset_observed", "lan_service_observations", ["lan_asset_id", "observed_at"])


def downgrade() -> None:
    op.drop_index("idx_lan_services_asset_observed", table_name="lan_service_observations")
    op.drop_table("lan_service_observations")
    op.drop_index("idx_lan_telemetry_asset_collected", table_name="lan_asset_telemetry")
    op.drop_table("lan_asset_telemetry")
    op.drop_index("idx_lan_assets_mac", table_name="lan_assets")
    op.drop_index("idx_lan_assets_last_seen", table_name="lan_assets")
    op.drop_index("idx_lan_assets_status", table_name="lan_assets")
    op.drop_table("lan_assets")
