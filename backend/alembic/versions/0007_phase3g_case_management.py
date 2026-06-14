"""Phase 3G investigation workflow and case management.

Revision ID: 0007_phase3g_case_management
Revises: 0006_phase2d_reports
Create Date: 2026-05-28

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_phase3g_case_management"
down_revision: Union[str, None] = "0006_phase2d_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_investigations_status",
        "investigations",
        type_="check",
    )
    op.execute("UPDATE investigations SET status = 'remediated' WHERE status = 'completed'")
    op.create_check_constraint(
        "ck_investigations_status",
        "investigations",
        "status IN ("
        "'draft', 'active', 'monitoring', 'review', 'remediated', 'archived'"
        ")",
    )

    op.create_table(
        "investigation_workflow_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_workflow_events_investigation",
        "investigation_workflow_events",
        ["investigation_id"],
    )
    op.create_index(
        "idx_workflow_events_created",
        "investigation_workflow_events",
        [sa.text("created_at DESC")],
    )

    op.create_table(
        "investigation_notes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "note_type",
            sa.String(length=30),
            server_default="analyst",
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
            "note_type IN ("
            "'analyst', 'evidence', 'recommendation', 'executive', "
            "'remediation'"
            ")",
            name="ck_investigation_notes_type",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_investigation_notes_investigation",
        "investigation_notes",
        ["investigation_id"],
    )
    op.create_index("idx_investigation_notes_author", "investigation_notes", ["author_id"])
    op.create_index(
        "idx_investigation_notes_created",
        "investigation_notes",
        [sa.text("created_at DESC")],
    )

    op.create_table(
        "investigation_tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="todo", nullable=False),
        sa.Column(
            "priority",
            sa.String(length=20),
            server_default="medium",
            nullable=False,
        ),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due_date", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('todo', 'in_progress', 'blocked', 'completed')",
            name="ck_investigation_tasks_status",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="ck_investigation_tasks_priority",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_investigation_tasks_investigation",
        "investigation_tasks",
        ["investigation_id"],
    )
    op.create_index(
        "idx_investigation_tasks_assigned",
        "investigation_tasks",
        ["assigned_to"],
    )
    op.create_index(
        "idx_investigation_tasks_status",
        "investigation_tasks",
        ["status"],
    )

    op.create_table(
        "investigation_evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence_type", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column(
            "confidence",
            sa.SmallInteger(),
            server_default="50",
            nullable=False,
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("analyst_comment", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            "confidence BETWEEN 0 AND 100",
            name="ck_evidence_confidence",
        ),
        sa.CheckConstraint(
            "evidence_type IN ("
            "'recon', 'dns', 'infrastructure', 'screenshot', 'report', "
            "'correlation', 'finding', 'threat_intel', 'analyst_note'"
            ")",
            name="ck_investigation_evidence_type",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["investigation_notes.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["investigation_tasks.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_investigation_evidence_investigation",
        "investigation_evidence",
        ["investigation_id"],
    )
    op.create_index(
        "idx_investigation_evidence_finding",
        "investigation_evidence",
        ["finding_id"],
    )
    op.create_index(
        "idx_investigation_evidence_note",
        "investigation_evidence",
        ["note_id"],
    )
    op.create_index(
        "idx_investigation_evidence_task",
        "investigation_evidence",
        ["task_id"],
    )
    op.create_index(
        "idx_investigation_evidence_created",
        "investigation_evidence",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_investigation_evidence_created", "investigation_evidence")
    op.drop_index("idx_investigation_evidence_task", "investigation_evidence")
    op.drop_index("idx_investigation_evidence_note", "investigation_evidence")
    op.drop_index("idx_investigation_evidence_finding", "investigation_evidence")
    op.drop_index("idx_investigation_evidence_investigation", "investigation_evidence")
    op.drop_table("investigation_evidence")

    op.drop_index("idx_investigation_tasks_status", "investigation_tasks")
    op.drop_index("idx_investigation_tasks_assigned", "investigation_tasks")
    op.drop_index("idx_investigation_tasks_investigation", "investigation_tasks")
    op.drop_table("investigation_tasks")

    op.drop_index("idx_investigation_notes_created", "investigation_notes")
    op.drop_index("idx_investigation_notes_author", "investigation_notes")
    op.drop_index("idx_investigation_notes_investigation", "investigation_notes")
    op.drop_table("investigation_notes")

    op.drop_index("idx_workflow_events_created", "investigation_workflow_events")
    op.drop_index("idx_workflow_events_investigation", "investigation_workflow_events")
    op.drop_table("investigation_workflow_events")

    op.drop_constraint(
        "ck_investigations_status",
        "investigations",
        type_="check",
    )
    op.execute("UPDATE investigations SET status = 'completed' WHERE status = 'remediated'")
    op.create_check_constraint(
        "ck_investigations_status",
        "investigations",
        "status IN ('draft', 'active', 'completed', 'archived')",
    )
