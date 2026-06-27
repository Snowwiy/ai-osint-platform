"""Add case collaboration and operational coordination.

Revision ID: 0017_phase4h_collaboration
Revises: 0016_phase4g_reporting
Create Date: 2026-06-14

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_phase4h_collaboration"
down_revision: str | None = "0016_phase4g_reporting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE investigation_members AS member
        SET role = 'analyst', updated_at = now()
        FROM investigations AS investigation
        WHERE member.investigation_id = investigation.id
          AND member.role = 'owner'
          AND member.user_id <> investigation.owner_id
        """
    )
    op.drop_constraint(
        "ck_investigations_status",
        "investigations",
        type_="check",
    )
    op.execute(
        """
        UPDATE investigations
        SET status = CASE status
            WHEN 'draft' THEN 'intake'
            WHEN 'triage' THEN 'active'
            WHEN 'validated' THEN 'validation'
            WHEN 'review' THEN 'validation'
            WHEN 'remediated' THEN 'completed'
            ELSE status
        END
        """
    )
    op.execute(
        """
        UPDATE investigation_workflow_events
        SET from_status = CASE from_status
                WHEN 'draft' THEN 'intake'
                WHEN 'triage' THEN 'active'
                WHEN 'validated' THEN 'validation'
                WHEN 'review' THEN 'validation'
                WHEN 'remediated' THEN 'completed'
                ELSE from_status
            END,
            to_status = CASE to_status
                WHEN 'draft' THEN 'intake'
                WHEN 'triage' THEN 'active'
                WHEN 'validated' THEN 'validation'
                WHEN 'review' THEN 'validation'
                WHEN 'remediated' THEN 'completed'
                ELSE to_status
            END
        """
    )
    op.alter_column(
        "investigations",
        "status",
        server_default="intake",
    )
    op.create_check_constraint(
        "ck_investigations_status",
        "investigations",
        "status IN ("
        "'intake', 'active', 'monitoring', 'remediation', "
        "'validation', 'completed', 'archived'"
        ")",
    )

    op.drop_constraint(
        "ck_investigation_tasks_status",
        "investigation_tasks",
        type_="check",
    )
    op.execute(
        """
        UPDATE investigation_tasks
        SET status = CASE status
            WHEN 'open' THEN 'todo'
            WHEN 'cancelled' THEN 'completed'
            ELSE status
        END,
        completed_at = CASE
            WHEN status = 'cancelled' AND completed_at IS NULL THEN now()
            ELSE completed_at
        END
        """
    )
    op.alter_column(
        "investigation_tasks",
        "status",
        server_default="todo",
    )
    op.create_check_constraint(
        "ck_investigation_tasks_status",
        "investigation_tasks",
        "status IN ('todo', 'in_progress', 'blocked', 'validation', 'completed')",
    )
    op.add_column(
        "investigation_tasks",
        sa.Column("blockers", sa.Text(), nullable=True),
    )
    op.add_column(
        "investigation_tasks",
        sa.Column(
            "playbook_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_investigation_tasks_playbook_run",
        "investigation_tasks",
        "playbook_runs",
        ["playbook_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_investigation_tasks_playbook_run",
        "investigation_tasks",
        ["playbook_run_id"],
    )

    op.drop_constraint(
        "ck_investigation_notes_type",
        "investigation_notes",
        type_="check",
    )
    op.create_check_constraint(
        "ck_investigation_notes_type",
        "investigation_notes",
        "note_type IN ("
        "'analyst_note', 'triage_note', 'remediation_note', "
        "'escalation_note', 'validation_note', 'closure_note', "
        "'evidence_note', 'executive_note', 'timeline_note'"
        ")",
    )
    op.add_column(
        "investigation_notes",
        sa.Column(
            "visibility",
            sa.String(length=20),
            server_default="investigation",
            nullable=False,
        ),
    )
    op.add_column(
        "investigation_notes",
        sa.Column(
            "references",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_investigation_notes_visibility",
        "investigation_notes",
        "visibility IN ('investigation', 'owners')",
    )

    op.create_table(
        "investigation_handoffs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "investigation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "previous_owner_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "new_owner_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "initiated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("context_transfer", sa.Text(), nullable=True),
        sa.Column("pending_work_summary", sa.Text(), nullable=True),
        sa.Column("unresolved_findings_summary", sa.Text(), nullable=True),
        sa.Column("remediation_status_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["previous_owner_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["new_owner_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["initiated_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_investigation_handoffs_investigation",
        "investigation_handoffs",
        ["investigation_id"],
    )
    op.create_index(
        "idx_investigation_handoffs_new_owner",
        "investigation_handoffs",
        ["new_owner_id"],
    )
    op.create_index(
        "idx_investigation_handoffs_created",
        "investigation_handoffs",
        [sa.text("created_at DESC")],
    )

    op.create_table(
        "investigation_escalations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "investigation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("level", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "level IN ("
            "'informational', 'analyst_review', 'senior_review', 'urgent_review'"
            ")",
            name="ck_investigation_escalations_level",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_investigation_escalations_investigation",
        "investigation_escalations",
        ["investigation_id"],
    )
    op.create_index(
        "idx_investigation_escalations_level",
        "investigation_escalations",
        ["level"],
    )
    op.create_index(
        "idx_investigation_escalations_created",
        "investigation_escalations",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_investigation_escalations_created",
        table_name="investigation_escalations",
    )
    op.drop_index(
        "idx_investigation_escalations_level",
        table_name="investigation_escalations",
    )
    op.drop_index(
        "idx_investigation_escalations_investigation",
        table_name="investigation_escalations",
    )
    op.drop_table("investigation_escalations")

    op.drop_index(
        "idx_investigation_handoffs_created",
        table_name="investigation_handoffs",
    )
    op.drop_index(
        "idx_investigation_handoffs_new_owner",
        table_name="investigation_handoffs",
    )
    op.drop_index(
        "idx_investigation_handoffs_investigation",
        table_name="investigation_handoffs",
    )
    op.drop_table("investigation_handoffs")

    op.drop_constraint(
        "ck_investigation_notes_visibility",
        "investigation_notes",
        type_="check",
    )
    op.drop_column("investigation_notes", "references")
    op.drop_column("investigation_notes", "visibility")
    op.drop_constraint(
        "ck_investigation_notes_type",
        "investigation_notes",
        type_="check",
    )
    op.create_check_constraint(
        "ck_investigation_notes_type",
        "investigation_notes",
        "note_type IN ("
        "'analyst_note', 'evidence_note', 'remediation_note', "
        "'executive_note', 'timeline_note'"
        ")",
    )

    op.drop_index(
        "idx_investigation_tasks_playbook_run",
        table_name="investigation_tasks",
    )
    op.drop_constraint(
        "fk_investigation_tasks_playbook_run",
        "investigation_tasks",
        type_="foreignkey",
    )
    op.drop_column("investigation_tasks", "playbook_run_id")
    op.drop_column("investigation_tasks", "blockers")
    op.drop_constraint(
        "ck_investigation_tasks_status",
        "investigation_tasks",
        type_="check",
    )
    op.execute(
        """
        UPDATE investigation_tasks
        SET status = CASE status
            WHEN 'todo' THEN 'open'
            WHEN 'validation' THEN 'in_progress'
            ELSE status
        END
        """
    )
    op.alter_column(
        "investigation_tasks",
        "status",
        server_default="open",
    )
    op.create_check_constraint(
        "ck_investigation_tasks_status",
        "investigation_tasks",
        "status IN ("
        "'open', 'in_progress', 'blocked', 'completed', 'cancelled', 'todo'"
        ")",
    )

    op.drop_constraint(
        "ck_investigations_status",
        "investigations",
        type_="check",
    )
    op.execute(
        """
        UPDATE investigations
        SET status = CASE status
            WHEN 'intake' THEN 'draft'
            WHEN 'validation' THEN 'validated'
            WHEN 'completed' THEN 'remediated'
            ELSE status
        END
        """
    )
    op.alter_column(
        "investigations",
        "status",
        server_default="active",
    )
    op.create_check_constraint(
        "ck_investigations_status",
        "investigations",
        "status IN ("
        "'draft', 'active', 'triage', 'monitoring', 'remediation', "
        "'validated', 'archived', 'review', 'remediated'"
        ")",
    )
