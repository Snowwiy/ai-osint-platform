"""Add persistent native jobs, worker leases, and native auth state.

Revision ID: 0040_phase5bi_native_jobs
Revises: 0039_phase5bh_service_policy
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

revision: str = "0040_phase5bi_native_jobs"
down_revision: str | None = "0039_phase5bh_service_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("job_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column(
            "payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("result_summary", sa.String(255)),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "scheduled_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", TIMESTAMP(timezone=True)),
        sa.Column("finished_at", TIMESTAMP(timezone=True)),
        sa.Column("heartbeat_at", TIMESTAMP(timezone=True)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("next_retry_at", TIMESTAMP(timezone=True)),
        sa.Column("last_error_code", sa.String(40)),
        sa.Column("last_error_summary", sa.String(255)),
        sa.Column("dedupe_key", sa.String(160)),
        sa.Column(
            "requested_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "investigation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("investigations.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "asset_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lan_assets.id", ondelete="SET NULL"),
        ),
        sa.Column("worker_id", sa.String(100)),
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.CheckConstraint(
            "status IN ('queued','scheduled','running','completed','failed',"
            "'retry_wait','cancel_requested','cancelled')",
            name="ck_background_jobs_status",
        ),
        sa.CheckConstraint(
            "priority BETWEEN 0 AND 100", name="ck_background_jobs_priority"
        ),
        sa.CheckConstraint(
            "progress BETWEEN 0 AND 100", name="ck_background_jobs_progress"
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 11",
            name="ck_background_jobs_attempts",
        ),
    )
    op.create_index(
        "idx_background_jobs_claim",
        "background_jobs",
        ["status", "priority", "scheduled_at"],
    )
    op.create_index(
        "idx_background_jobs_requested",
        "background_jobs",
        ["requested_by_user_id", "created_at"],
    )
    op.create_index(
        "uq_background_jobs_active_dedupe",
        "background_jobs",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text(
            "dedupe_key IS NOT NULL AND status IN "
            "('queued','scheduled','running','retry_wait','cancel_requested')"
        ),
    )
    op.create_table(
        "background_job_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("background_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column(
            "occurred_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("worker_id", sa.String(100)),
        sa.Column("detail", sa.String(255), nullable=False),
    )
    op.create_index(
        "idx_background_job_events_job_time",
        "background_job_events",
        ["job_id", "occurred_at"],
    )
    op.create_table(
        "native_worker_heartbeats",
        sa.Column("worker_id", sa.String(100), primary_key=True),
        sa.Column(
            "started_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "heartbeat_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "stopping", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.create_table(
        "native_auth_state",
        sa.Column("key", sa.String(180), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_native_auth_state_expires", "native_auth_state", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_native_auth_state_expires", table_name="native_auth_state")
    op.drop_table("native_auth_state")
    op.drop_table("native_worker_heartbeats")
    op.drop_index(
        "idx_background_job_events_job_time", table_name="background_job_events"
    )
    op.drop_table("background_job_events")
    op.drop_index("uq_background_jobs_active_dedupe", table_name="background_jobs")
    op.drop_index("idx_background_jobs_requested", table_name="background_jobs")
    op.drop_index("idx_background_jobs_claim", table_name="background_jobs")
    op.drop_table("background_jobs")
