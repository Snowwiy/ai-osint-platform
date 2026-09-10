"""Add defensive vulnerability baseline and LAN asset criticality.

Revision ID: 0030_phase5z_base
Revises: 0029_phase5y_lan
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_phase5z_base"
down_revision: str | None = "0029_phase5y_lan"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lan_assets", sa.Column("criticality", sa.String(length=20), server_default="medium", nullable=False))
    op.add_column("lan_assets", sa.Column("owner", sa.String(length=255), nullable=True))
    op.add_column("lan_assets", sa.Column("business_function", sa.String(length=255), nullable=True))
    op.add_column("lan_assets", sa.Column("environment", sa.String(length=80), nullable=True))
    op.create_check_constraint(
        "ck_lan_assets_criticality", "lan_assets",
        "criticality IN ('low', 'medium', 'high', 'critical')",
    )

    op.create_table(
        "vulnerability_baseline_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("lan_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rule_key", sa.String(length=80), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.String(length=20), server_default="medium", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="open", nullable=False),
        sa.Column("source", sa.String(length=80), server_default="local_baseline", nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("remediation_owner", sa.String(length=255), nullable=True),
        sa.Column("remediation_due_date", postgresql.DATE(), nullable=True),
        sa.Column("first_seen", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("severity IN ('info', 'low', 'medium', 'high', 'critical')", name="ck_vulnerability_baseline_severity"),
        sa.CheckConstraint("confidence IN ('low', 'medium', 'high')", name="ck_vulnerability_baseline_confidence"),
        sa.CheckConstraint("status IN ('open', 'acknowledged', 'in_progress', 'resolved', 'false_positive')", name="ck_vulnerability_baseline_status"),
        sa.ForeignKeyConstraint(["lan_asset_id"], ["lan_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_vulnerability_baseline_dedupe"),
    )
    op.create_index("idx_vulnerability_baseline_asset", "vulnerability_baseline_findings", ["lan_asset_id"])
    op.create_index("idx_vulnerability_baseline_investigation", "vulnerability_baseline_findings", ["investigation_id"])
    op.create_index("idx_vulnerability_baseline_severity", "vulnerability_baseline_findings", ["severity"])
    op.create_index("idx_vulnerability_baseline_status", "vulnerability_baseline_findings", ["status"])
    op.create_index("idx_vulnerability_baseline_due", "vulnerability_baseline_findings", ["remediation_due_date"])


def downgrade() -> None:
    op.drop_index("idx_vulnerability_baseline_due", table_name="vulnerability_baseline_findings")
    op.drop_index("idx_vulnerability_baseline_status", table_name="vulnerability_baseline_findings")
    op.drop_index("idx_vulnerability_baseline_severity", table_name="vulnerability_baseline_findings")
    op.drop_index("idx_vulnerability_baseline_investigation", table_name="vulnerability_baseline_findings")
    op.drop_index("idx_vulnerability_baseline_asset", table_name="vulnerability_baseline_findings")
    op.drop_table("vulnerability_baseline_findings")
    op.drop_constraint("ck_lan_assets_criticality", "lan_assets", type_="check")
    op.drop_column("lan_assets", "environment")
    op.drop_column("lan_assets", "business_function")
    op.drop_column("lan_assets", "owner")
    op.drop_column("lan_assets", "criticality")
