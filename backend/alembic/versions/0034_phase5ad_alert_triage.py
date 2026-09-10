"""Add lightweight monitoring alert triage.

Revision ID: 0034_phase5ad_triage
Revises: 0033_phase5ac_history
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034_phase5ad_triage"
down_revision: str | None = "0033_phase5ac_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitoring_alert_triage",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("alert_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="new", nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("related_asset_id", sa.UUID(), nullable=True),
        sa.Column("related_finding_id", sa.UUID(), nullable=True),
        sa.Column("first_seen", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_seen", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("resolution_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("severity IN ('info', 'success', 'warning', 'critical')", name="ck_monitoring_alert_triage_severity"),
        sa.CheckConstraint("status IN ('new', 'triaged', 'investigating', 'muted', 'resolved', 'false_positive')", name="ck_monitoring_alert_triage_status"),
        sa.ForeignKeyConstraint(["alert_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_asset_id"], ["lan_assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_finding_id"], ["vulnerability_baseline_findings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id"),
    )
    op.create_index("idx_monitoring_triage_status", "monitoring_alert_triage", ["status"])
    op.create_index("idx_monitoring_triage_owner", "monitoring_alert_triage", ["owner_id"])
    op.create_index("idx_monitoring_triage_asset", "monitoring_alert_triage", ["related_asset_id"])
    op.create_index("idx_monitoring_triage_last_seen", "monitoring_alert_triage", [sa.text("last_seen DESC")])


def downgrade() -> None:
    op.drop_index("idx_monitoring_triage_last_seen", table_name="monitoring_alert_triage")
    op.drop_index("idx_monitoring_triage_asset", table_name="monitoring_alert_triage")
    op.drop_index("idx_monitoring_triage_owner", table_name="monitoring_alert_triage")
    op.drop_index("idx_monitoring_triage_status", table_name="monitoring_alert_triage")
    op.drop_table("monitoring_alert_triage")
