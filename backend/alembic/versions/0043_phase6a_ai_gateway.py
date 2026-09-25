"""Add user-owned AI model preferences and chat history.

Revision ID: 0043_phase6a_ai_gateway
Revises: 0042_phase5br_knowledge_sources
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0043_phase6a_ai_gateway"
down_revision: str | None = "0042_phase5br_knowledge_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_model_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selected_model_id", sa.String(300), nullable=True),
        sa.Column("preferred_local_model_id", sa.String(300), nullable=True),
        sa.Column("preferred_free_model_id", sa.String(300), nullable=True),
        sa.Column(
            "execution_mode", sa.String(24), server_default="free_only", nullable=False
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "execution_mode IN ('free_only', 'local_only', 'any_configured')",
            name="ck_ai_model_preferences_execution_mode",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "ai_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "title", sa.String(120), server_default="New AI chat", nullable=False
        ),
        sa.Column("provider_id", sa.String(120), nullable=False),
        sa.Column("model_id", sa.String(240), nullable=False),
        sa.Column("execution_type", sa.String(12), nullable=False),
        sa.Column(
            "context_policy",
            sa.String(24),
            server_default="verified_only",
            nullable=False,
        ),
        sa.Column("status", sa.String(16), server_default="ready", nullable=False),
        sa.Column("external_session_id", sa.String(200), nullable=True),
        sa.Column(
            "archived", sa.Boolean(), server_default=sa.text("false"), nullable=False
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
            "status IN ('ready', 'running', 'failed', 'cancelled')",
            name="ck_ai_sessions_status",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ai_sessions_owner_updated",
        "ai_sessions",
        ["owner_id", sa.text("updated_at DESC")],
    )
    op.create_table(
        "ai_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), server_default="completed", nullable=False),
        sa.Column("provider_id", sa.String(120), nullable=True),
        sa.Column("model_id", sa.String(240), nullable=True),
        sa.Column("execution_type", sa.String(12), nullable=True),
        sa.Column(
            "context_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "supplied_citations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_ai_messages_role"),
        sa.ForeignKeyConstraint(["session_id"], ["ai_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "sequence", name="uq_ai_messages_session_sequence"
        ),
    )
    op.create_index(
        "idx_ai_messages_session_created", "ai_messages", ["session_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_ai_messages_session_created", table_name="ai_messages")
    op.drop_table("ai_messages")
    op.drop_index("idx_ai_sessions_owner_updated", table_name="ai_sessions")
    op.drop_table("ai_sessions")
    op.drop_table("ai_model_preferences")
