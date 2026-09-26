"""Persist local AI benchmark summaries and offline preferences.

Revision ID: 0046_phase6e_local_ai
Revises: 0045_phase6d_action_gateway
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0046_phase6e_local_ai"
down_revision: str | None = "0045_phase6d_action_gateway"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_ai_model_preferences_execution_mode",
        "ai_model_preferences",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ai_model_preferences_execution_mode",
        "ai_model_preferences",
        "execution_mode IN ('local_first', 'free_only', 'local_only', "
        "'any_configured')",
    )
    op.alter_column(
        "ai_model_preferences",
        "execution_mode",
        existing_type=sa.String(length=24),
        server_default="local_first",
    )
    op.add_column(
        "ai_model_preferences",
        sa.Column(
            "offline_ai_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "ai_model_preferences",
        sa.Column(
            "routing_mode",
            sa.String(length=24),
            server_default="manual",
            nullable=False,
        ),
    )
    op.add_column(
        "ai_model_preferences",
        sa.Column(
            "task_model_routes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_ai_model_preferences_routing_mode",
        "ai_model_preferences",
        "routing_mode IN ('manual', 'recommended', 'automatic_local')",
    )
    op.add_column(
        "ai_messages",
        sa.Column("requested_model_id", sa.String(length=300), nullable=True),
    )
    op.add_column(
        "ai_messages",
        sa.Column("routing_reason", sa.String(length=120), nullable=True),
    )
    op.create_table(
        "ai_benchmark_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_id", sa.String(length=300), nullable=False),
        sa.Column("runtime_id", sa.String(length=80), nullable=False),
        sa.Column("hardware_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "hardware_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "profile_version",
            sa.String(length=24),
            server_default="1.0",
            nullable=False,
        ),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "started_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_ai_benchmark_results_status",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ai_benchmark_results_owner_started",
        "ai_benchmark_results",
        ["owner_id", sa.text("started_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_ai_benchmark_results_owner_started", table_name="ai_benchmark_results"
    )
    op.drop_table("ai_benchmark_results")
    op.drop_column("ai_messages", "routing_reason")
    op.drop_column("ai_messages", "requested_model_id")
    op.drop_constraint(
        "ck_ai_model_preferences_routing_mode",
        "ai_model_preferences",
        type_="check",
    )
    op.drop_column("ai_model_preferences", "task_model_routes")
    op.drop_column("ai_model_preferences", "routing_mode")
    op.execute(
        "UPDATE ai_model_preferences SET execution_mode = 'free_only' "
        "WHERE execution_mode = 'local_first'"
    )
    op.drop_constraint(
        "ck_ai_model_preferences_execution_mode",
        "ai_model_preferences",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ai_model_preferences_execution_mode",
        "ai_model_preferences",
        "execution_mode IN ('free_only', 'local_only', 'any_configured')",
    )
    op.alter_column(
        "ai_model_preferences",
        "execution_mode",
        existing_type=sa.String(length=24),
        server_default="free_only",
    )
    op.drop_column("ai_model_preferences", "offline_ai_enabled")
