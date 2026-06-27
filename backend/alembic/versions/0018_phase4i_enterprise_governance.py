"""Add enterprise governance and archive metadata.

Revision ID: 0018_phase4i_governance
Revises: 0017_phase4h_collaboration
Create Date: 2026-06-14

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_phase4i_governance"
down_revision: str | None = "0017_phase4h_collaboration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SETTINGS_ID = "50000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    admin_settings = op.create_table(
        "admin_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "general",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "security",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "retention",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "export_controls",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "report_branding",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "audit_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "feature_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
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
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(
        admin_settings,
        [
            {
                "id": _SETTINGS_ID,
                "general": {
                    "platform_name": "RavenTech OSINT",
                    "deployment_label": "Internal Defensive Use",
                    "support_contact": "",
                },
                "security": {
                    "classification_banner": "Internal Use Only",
                    "require_export_confirmation": True,
                },
                "retention": {
                    "investigations": "indefinite",
                    "audit_logs": "365_days",
                    "reports": "365_days",
                    "notes": "indefinite",
                    "tasks": "indefinite",
                    "exports": "365_days",
                },
                "export_controls": {
                    "allow_pdf_export": True,
                    "allow_docx_export": True,
                    "allow_html_export": True,
                    "allow_markdown_export": True,
                    "watermark_exports": False,
                    "include_audit_summary": True,
                    "include_evidence_appendix": True,
                    "redact_analyst_names": False,
                    "redact_internal_notes": False,
                },
                "report_branding": {
                    "company_name": "RavenTech",
                    "report_title_prefix": "",
                    "primary_color": "#7C3AED",
                    "secondary_color": "#111827",
                    "footer_text": "",
                    "confidentiality_label": "Internal Use Only",
                },
                "audit_policy": {
                    "audit_login_events": True,
                    "audit_report_downloads": True,
                    "audit_recon_runs": True,
                    "audit_member_changes": True,
                    "audit_failed_permissions": True,
                    "audit_data_exports": True,
                },
                "feature_flags": {
                    "enable_ai_analysis": True,
                    "enable_report_exports": True,
                    "enable_playbooks": True,
                    "enable_bulk_actions": True,
                    "enable_collaboration": True,
                    "enable_audit_exports": True,
                    "enable_advanced_dashboard": True,
                },
            }
        ],
    )
    op.add_column(
        "investigation_tasks",
        sa.Column(
            "archived_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_investigation_tasks_archived_at",
        "investigation_tasks",
        ["archived_at"],
    )
    op.add_column(
        "playbook_runs",
        sa.Column(
            "archived_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_playbook_runs_archived_at",
        "playbook_runs",
        ["archived_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_playbook_runs_archived_at", table_name="playbook_runs")
    op.drop_column("playbook_runs", "archived_at")
    op.drop_index(
        "idx_investigation_tasks_archived_at",
        table_name="investigation_tasks",
    )
    op.drop_column("investigation_tasks", "archived_at")
    op.drop_table("admin_settings")
