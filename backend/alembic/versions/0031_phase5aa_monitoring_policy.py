"""Add monitoring policies, alert suppressions, and maintenance windows.

Revision ID: 0031_phase5aa_policy
Revises: 0030_phase5z_base
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031_phase5aa_policy"
down_revision: str | None = "0030_phase5z_base"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitoring_policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("rule_key", sa.String(80), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("severity_override", sa.String(20), nullable=True),
        sa.Column("threshold_value", sa.Float(), nullable=True),
        sa.Column("threshold_unit", sa.String(30), nullable=True),
        sa.Column(
            "cooldown_minutes", sa.Integer(), server_default="240", nullable=False
        ),
        sa.Column("dedupe_key", sa.String(120), nullable=False),
        sa.Column(
            "max_alerts_per_rule", sa.Integer(), server_default="3", nullable=False
        ),
        sa.Column(
            "acknowledge_behavior",
            sa.String(30),
            server_default="keep_active",
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity_override IS NULL OR severity_override IN ('info', 'warning', 'critical')",
            name="ck_monitoring_policy_severity",
        ),
        sa.CheckConstraint(
            "threshold_value IS NULL OR threshold_value >= 0",
            name="ck_monitoring_policy_threshold",
        ),
        sa.CheckConstraint(
            "cooldown_minutes BETWEEN 1 AND 10080", name="ck_monitoring_policy_cooldown"
        ),
        sa.CheckConstraint(
            "max_alerts_per_rule BETWEEN 1 AND 100",
            name="ck_monitoring_policy_max_alerts",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_key", name="uq_monitoring_policy_rule_key"),
    )
    op.create_table(
        "maintenance_windows",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("start_time", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_time", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "affected_assets",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affected_services",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "suppress_alerts", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("end_time > start_time", name="ck_maintenance_window_range"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "alert_suppressions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(20), server_default="manual", nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("starts_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ends_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lifted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lifted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'maintenance')", name="ck_alert_suppression_source"
        ),
        sa.ForeignKeyConstraint(["alert_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lifted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_alert_suppression_alert_active",
        "alert_suppressions",
        ["alert_id", "active"],
    )


def downgrade() -> None:
    op.drop_index("idx_alert_suppression_alert_active", table_name="alert_suppressions")
    op.drop_table("alert_suppressions")
    op.drop_table("maintenance_windows")
    op.drop_table("monitoring_policies")
