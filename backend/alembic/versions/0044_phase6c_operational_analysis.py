"""Persist bounded, reproducible operational AI analyses.

Revision ID: 0044_phase6c_op_analysis
Revises: 0043_phase6a_ai_gateway
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0044_phase6c_op_analysis"
down_revision: str | None = "0043_phase6a_ai_gateway"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_ai_analyses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("workflow", sa.String(length=40), nullable=False),
        sa.Column("scope_type", sa.String(length=40), nullable=False),
        sa.Column("scope_id", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("evidence_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "window",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "model_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("bundle_sha256", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'completed_with_warnings')",
            name="ck_operational_ai_analysis_status",
        ),
        sa.CheckConstraint(
            "length(bundle_sha256) = 64",
            name="ck_operational_ai_analysis_bundle_hash",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_operational_ai_analysis_owner_created",
        "operational_ai_analyses",
        ["requested_by_user_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "uq_operational_ai_analysis_dedupe_key",
        "operational_ai_analyses",
        ["dedupe_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_operational_ai_analysis_dedupe_key",
        table_name="operational_ai_analyses",
    )
    op.drop_index(
        "idx_operational_ai_analysis_owner_created",
        table_name="operational_ai_analyses",
    )
    op.drop_table("operational_ai_analyses")
