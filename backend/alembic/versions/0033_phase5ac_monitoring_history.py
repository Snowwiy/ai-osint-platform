"""Add LAN monitoring change and service history.

Revision ID: 0033_phase5ac_history
Revises: 0032_phase5ab_ports
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033_phase5ac_history"
down_revision: str | None = "0032_phase5ab_ports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitoring_change_events",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("asset_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column(
            "severity", sa.String(length=20), server_default="info", nullable=False
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("old_value", sa.String(length=255), nullable=True),
        sa.Column("new_value", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column(
            "detected_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("acknowledged_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'low', 'medium', 'high', 'critical')",
            name="ck_monitoring_change_severity",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["lan_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_monitoring_changes_detected",
        "monitoring_change_events",
        [sa.text("detected_at DESC")],
    )
    op.create_index(
        "idx_monitoring_changes_asset_detected",
        "monitoring_change_events",
        ["asset_id", "detected_at"],
    )
    op.create_index(
        "idx_monitoring_changes_type", "monitoring_change_events", ["event_type"]
    )
    op.create_index(
        "idx_monitoring_changes_acknowledged",
        "monitoring_change_events",
        ["acknowledged_at"],
    )
    op.create_table(
        "service_observation_history",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column(
            "protocol", sa.String(length=8), server_default="tcp", nullable=False
        ),
        sa.Column("previous_status", sa.String(length=20), nullable=True),
        sa.Column("current_status", sa.String(length=20), nullable=False),
        sa.Column("service_name", sa.String(length=100), nullable=True),
        sa.Column("confidence", sa.Integer(), server_default="40", nullable=False),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 100", name="ck_service_history_confidence"
        ),
        sa.CheckConstraint("port BETWEEN 1 AND 65535", name="ck_service_history_port"),
        sa.CheckConstraint("protocol = 'tcp'", name="ck_service_history_protocol"),
        sa.CheckConstraint(
            "current_status IN ('open', 'closed', 'filtered', 'timeout', 'unknown')",
            name="ck_service_history_status",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["lan_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_service_history_asset_observed",
        "service_observation_history",
        ["asset_id", "observed_at"],
    )
    op.create_index(
        "idx_service_history_port", "service_observation_history", ["port", "protocol"]
    )


def downgrade() -> None:
    op.drop_index("idx_service_history_port", table_name="service_observation_history")
    op.drop_index(
        "idx_service_history_asset_observed", table_name="service_observation_history"
    )
    op.drop_table("service_observation_history")
    op.drop_index(
        "idx_monitoring_changes_acknowledged", table_name="monitoring_change_events"
    )
    op.drop_index("idx_monitoring_changes_type", table_name="monitoring_change_events")
    op.drop_index(
        "idx_monitoring_changes_asset_detected", table_name="monitoring_change_events"
    )
    op.drop_index(
        "idx_monitoring_changes_detected", table_name="monitoring_change_events"
    )
    op.drop_table("monitoring_change_events")
