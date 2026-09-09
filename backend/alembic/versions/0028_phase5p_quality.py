"""Add persistent data quality issues.

Revision ID: 0028_phase5p_quality
Revises: 0027_phase5o_search
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028_phase5p_quality"
down_revision: str | None = "0027_phase5o_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_quality_issues",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("issue_type", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("related_entity_type", sa.String(length=40), nullable=True),
        sa.Column("related_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("action_url", sa.String(length=500), nullable=True),
        sa.Column(
            "detected_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "acknowledged_at", postgresql.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
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
            "severity IN ('info', 'warning', 'high', 'critical')",
            name="ck_data_quality_issues_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved', 'ignored')",
            name="ck_data_quality_issues_status",
        ),
        sa.CheckConstraint(
            "entity_type IN ("
            "'investigation', 'engagement', 'scope_item', 'finding', "
            "'evidence', 'report', 'deliverable', 'closure', 'notification', "
            "'saved_view', 'user', 'audit_log', 'demo_data', 'system'"
            ")",
            name="ck_data_quality_issues_entity_type",
        ),
        sa.ForeignKeyConstraint(
            ["acknowledged_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_data_quality_issues_fingerprint",
        "data_quality_issues",
        ["fingerprint"],
        unique=True,
    )
    op.create_index(
        "idx_data_quality_issues_status_severity",
        "data_quality_issues",
        ["status", "severity"],
    )
    op.create_index(
        "idx_data_quality_issues_entity",
        "data_quality_issues",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "idx_data_quality_issues_type",
        "data_quality_issues",
        ["issue_type"],
    )
    op.create_index(
        "idx_data_quality_issues_detected",
        "data_quality_issues",
        [sa.text("detected_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("data_quality_issues")
