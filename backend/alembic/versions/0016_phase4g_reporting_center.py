"""Add enterprise report templates and lifecycle tracking.

Revision ID: 0016_phase4g_reporting
Revises: 0015_phase4f_operations
Create Date: 2026-06-14

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_phase4g_reporting"
down_revision: str | None = "0015_phase4f_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEMPLATES = (
    (
        "40000000-0000-4000-8000-000000000001",
        "Executive Summary",
        "Concise business risk, findings, remediation, and recommendations.",
        "executive",
        [
            "executive_summary",
            "scope",
            "authorization",
            "findings_summary",
            "severity_distribution",
            "remediation_progress",
            "framework_mapping",
            "appendix",
        ],
        True,
    ),
    (
        "40000000-0000-4000-8000-000000000002",
        "Technical Assessment",
        "Detailed defensive assessment with evidence, findings, and mappings.",
        "technical",
        [
            "executive_summary",
            "scope",
            "authorization",
            "findings_summary",
            "severity_distribution",
            "evidence_chains",
            "recurring_evidence",
            "related_investigations",
            "analyst_notes",
            "task_summary",
            "timeline_summary",
            "audit_summary",
            "framework_mapping",
            "appendix",
        ],
        True,
    ),
    (
        "40000000-0000-4000-8000-000000000003",
        "Remediation Report",
        "Remediation ownership, tasks, verification, and unresolved risk.",
        "remediation",
        [
            "executive_summary",
            "findings_summary",
            "remediation_progress",
            "playbook_progress",
            "task_summary",
            "analyst_notes",
            "timeline_summary",
            "appendix",
        ],
        True,
    ),
    (
        "40000000-0000-4000-8000-000000000004",
        "Evidence Appendix",
        "Evidence chains, recurring evidence, related cases, and citations.",
        "evidence_appendix",
        [
            "scope",
            "authorization",
            "evidence_chains",
            "recurring_evidence",
            "related_investigations",
            "timeline_summary",
            "audit_summary",
            "appendix",
        ],
        True,
    ),
    (
        "40000000-0000-4000-8000-000000000005",
        "Compliance Mapping Report",
        "Defensive findings mapped to stored framework guidance.",
        "compliance_mapping",
        [
            "executive_summary",
            "findings_summary",
            "severity_distribution",
            "framework_mapping",
            "remediation_progress",
            "appendix",
        ],
        True,
    ),
    (
        "40000000-0000-4000-8000-000000000006",
        "Playbook Progress Report",
        "Playbook execution, remediation tasks, evidence, and analyst notes.",
        "playbook_progress",
        [
            "findings_summary",
            "remediation_progress",
            "playbook_progress",
            "evidence_chains",
            "analyst_notes",
            "task_summary",
            "timeline_summary",
            "appendix",
        ],
        True,
    ),
    (
        "40000000-0000-4000-8000-000000000007",
        "Operational Dashboard Report",
        "Investigation posture, triage, workload, and recurring infrastructure.",
        "operational_dashboard",
        [
            "executive_summary",
            "severity_distribution",
            "remediation_progress",
            "recurring_evidence",
            "related_investigations",
            "task_summary",
            "timeline_summary",
            "audit_summary",
            "appendix",
        ],
        True,
    ),
)


def upgrade() -> None:
    op.create_table(
        "report_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column(
            "sections",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "idx_report_templates_active_type",
        "report_templates",
        ["is_active", "report_type"],
    )

    op.drop_constraint("ck_reports_format", "reports", type_="check")
    op.drop_constraint("ck_reports_status", "reports", type_="check")
    op.drop_constraint("ck_reports_type", "reports", type_="check")
    op.execute("UPDATE reports SET report_format = 'html' WHERE report_format = 'json'")
    op.execute("UPDATE reports SET status = 'queued' WHERE status = 'pending'")
    op.alter_column(
        "reports",
        "report_type",
        existing_type=sa.String(length=20),
        type_=sa.String(length=40),
        existing_nullable=False,
    )
    op.add_column(
        "reports",
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "reports",
        sa.Column("progress_label", sa.String(length=120), nullable=True),
    )
    op.add_column("reports", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.add_column(
        "reports",
        sa.Column(
            "retry_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "generated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "archived_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_reports_template_id_report_templates",
        "reports",
        "report_templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_reports_template_id", "reports", ["template_id"])
    op.create_index(
        "idx_reports_status_created_at",
        "reports",
        ["status", "created_at"],
    )
    op.create_check_constraint(
        "ck_reports_format",
        "reports",
        "report_format IN ('html', 'md', 'pdf', 'docx')",
    )
    op.create_check_constraint(
        "ck_reports_status",
        "reports",
        "status IN ('queued', 'generating', 'ready', 'failed', 'archived')",
    )
    op.create_check_constraint(
        "ck_reports_type",
        "reports",
        "report_type IN ("
        "'executive', 'technical', 'remediation', 'evidence_appendix', "
        "'compliance_mapping', 'playbook_progress', 'operational_dashboard'"
        ")",
    )
    op.execute(
        "UPDATE reports SET generated_at = created_at "
        "WHERE status = 'ready' AND generated_at IS NULL"
    )
    _seed_templates()


def downgrade() -> None:
    op.drop_index("idx_reports_status_created_at", table_name="reports")
    op.drop_index("idx_reports_template_id", table_name="reports")
    op.drop_constraint(
        "fk_reports_template_id_report_templates",
        "reports",
        type_="foreignkey",
    )
    op.drop_constraint("ck_reports_type", "reports", type_="check")
    op.drop_constraint("ck_reports_status", "reports", type_="check")
    op.drop_constraint("ck_reports_format", "reports", type_="check")
    op.execute(
        "UPDATE reports SET report_type = 'technical' "
        "WHERE report_type NOT IN ('executive', 'technical')"
    )
    op.execute("UPDATE reports SET status = 'failed' WHERE status = 'archived'")
    op.execute("UPDATE reports SET status = 'pending' WHERE status = 'queued'")
    op.execute("UPDATE reports SET report_format = 'html' WHERE report_format = 'md'")
    op.execute("UPDATE reports SET report_format = 'pdf' WHERE report_format = 'docx'")
    op.drop_column("reports", "archived_at")
    op.drop_column("reports", "generated_at")
    op.drop_column("reports", "retry_count")
    op.drop_column("reports", "failure_reason")
    op.drop_column("reports", "progress_label")
    op.drop_column("reports", "template_id")
    op.alter_column(
        "reports",
        "report_type",
        existing_type=sa.String(length=40),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_reports_format",
        "reports",
        "report_format IN ('pdf', 'html', 'json')",
    )
    op.create_check_constraint(
        "ck_reports_status",
        "reports",
        "status IN ('pending', 'generating', 'ready', 'failed')",
    )
    op.create_check_constraint(
        "ck_reports_type",
        "reports",
        "report_type IN ('executive', 'technical')",
    )
    op.drop_index("idx_report_templates_active_type", table_name="report_templates")
    op.drop_table("report_templates")


def _seed_templates() -> None:
    template_table = sa.table(
        "report_templates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("report_type", sa.String()),
        sa.column("sections", postgresql.JSONB()),
        sa.column("is_default", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        template_table,
        [
            {
                "id": template_id,
                "name": name,
                "description": description,
                "report_type": report_type,
                "sections": sections,
                "is_default": is_default,
                "is_active": True,
            }
            for (
                template_id,
                name,
                description,
                report_type,
                sections,
                is_default,
            ) in _TEMPLATES
        ],
    )
