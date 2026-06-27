"""Phase 4D analyst intelligence and investigation productivity.

Revision ID: 0013_phase4d_productivity
Revises: 0012_phase4c_defensive_playbooks
Create Date: 2026-06-14

"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_phase4d_productivity"
down_revision: str | None = "0012_phase4c_defensive_playbooks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_TAGS = (
    ("30000000-0000-4000-8000-000000000001", "phishing", "rose"),
    ("30000000-0000-4000-8000-000000000002", "infrastructure", "cyan"),
    ("30000000-0000-4000-8000-000000000003", "cloud", "blue"),
    ("30000000-0000-4000-8000-000000000004", "exposed-service", "orange"),
    ("30000000-0000-4000-8000-000000000005", "dns", "teal"),
    ("30000000-0000-4000-8000-000000000006", "malware-analysis", "red"),
    ("30000000-0000-4000-8000-000000000007", "threat-intel", "violet"),
    ("30000000-0000-4000-8000-000000000008", "investigation-review", "amber"),
    ("30000000-0000-4000-8000-000000000009", "high-priority", "rose"),
    ("30000000-0000-4000-8000-000000000010", "monitoring", "emerald"),
)


def upgrade() -> None:
    _upgrade_notes()
    _upgrade_investigations()
    _create_bookmarks()
    _create_tags()


def downgrade() -> None:
    op.drop_table("investigation_tag_links")
    op.drop_table("investigation_tags")
    op.drop_table("evidence_bookmarks")

    op.drop_index("idx_investigations_priority", table_name="investigations")
    op.drop_constraint(
        "ck_investigations_priority",
        "investigations",
        type_="check",
    )
    op.drop_column("investigations", "due_date")
    op.drop_column("investigations", "business_impact")
    op.drop_column("investigations", "priority")

    op.drop_index("idx_investigation_notes_pinned", table_name="investigation_notes")
    op.drop_index(
        "idx_investigation_notes_created_by",
        table_name="investigation_notes",
    )
    op.create_index(
        "idx_investigation_notes_author",
        "investigation_notes",
        ["created_by"],
    )
    op.drop_constraint(
        "fk_investigation_notes_updated_by_users",
        "investigation_notes",
        type_="foreignkey",
    )
    op.drop_column("investigation_notes", "archived")
    op.drop_column("investigation_notes", "pinned")
    op.drop_column("investigation_notes", "updated_by")
    op.drop_constraint(
        "ck_investigation_notes_type",
        "investigation_notes",
        type_="check",
    )
    op.execute(
        "UPDATE investigation_notes SET note_type = CASE note_type "
        "WHEN 'analyst_note' THEN 'analyst' "
        "WHEN 'evidence_note' THEN 'evidence' "
        "WHEN 'remediation_note' THEN 'remediation' "
        "WHEN 'executive_note' THEN 'executive' "
        "ELSE 'analyst' END"
    )
    op.create_check_constraint(
        "ck_investigation_notes_type",
        "investigation_notes",
        "note_type IN ("
        "'analyst', 'evidence', 'recommendation', 'executive', 'remediation'"
        ")",
    )
    op.alter_column("investigation_notes", "content", new_column_name="note")
    op.alter_column(
        "investigation_notes",
        "created_by",
        new_column_name="author_id",
    )


def _upgrade_notes() -> None:
    op.drop_constraint(
        "ck_investigation_notes_type",
        "investigation_notes",
        type_="check",
    )
    op.drop_index("idx_investigation_notes_author", table_name="investigation_notes")
    op.alter_column(
        "investigation_notes",
        "author_id",
        new_column_name="created_by",
    )
    op.alter_column("investigation_notes", "note", new_column_name="content")
    op.execute(
        "UPDATE investigation_notes SET note_type = CASE note_type "
        "WHEN 'analyst' THEN 'analyst_note' "
        "WHEN 'evidence' THEN 'evidence_note' "
        "WHEN 'recommendation' THEN 'analyst_note' "
        "WHEN 'executive' THEN 'executive_note' "
        "WHEN 'remediation' THEN 'remediation_note' "
        "ELSE 'analyst_note' END"
    )
    op.create_check_constraint(
        "ck_investigation_notes_type",
        "investigation_notes",
        "note_type IN ("
        "'analyst_note', 'evidence_note', 'remediation_note', "
        "'executive_note', 'timeline_note'"
        ")",
    )
    op.add_column(
        "investigation_notes",
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "investigation_notes",
        sa.Column(
            "pinned",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "investigation_notes",
        sa.Column(
            "archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_investigation_notes_updated_by_users",
        "investigation_notes",
        "users",
        ["updated_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_investigation_notes_created_by",
        "investigation_notes",
        ["created_by"],
    )
    op.create_index(
        "idx_investigation_notes_pinned",
        "investigation_notes",
        ["investigation_id", "pinned"],
    )


def _upgrade_investigations() -> None:
    op.add_column(
        "investigations",
        sa.Column(
            "priority",
            sa.String(length=10),
            server_default="medium",
            nullable=False,
        ),
    )
    op.add_column(
        "investigations",
        sa.Column("business_impact", sa.Text(), nullable=True),
    )
    op.add_column(
        "investigations",
        sa.Column("due_date", sa.Date(), nullable=True),
    )
    op.create_check_constraint(
        "ck_investigations_priority",
        "investigations",
        "priority IN ('low', 'medium', 'high', 'urgent')",
    )
    op.create_index(
        "idx_investigations_priority",
        "investigations",
        ["priority"],
    )


def _create_bookmarks() -> None:
    op.create_table(
        "evidence_bookmarks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "entity_id IS NOT NULL OR finding_id IS NOT NULL OR report_id IS NOT NULL",
            name="ck_evidence_bookmarks_link",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["recon_entities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("idx_evidence_bookmarks_investigation", ["investigation_id"]),
        ("idx_evidence_bookmarks_created_by", ["created_by"]),
        ("idx_evidence_bookmarks_entity", ["entity_id"]),
        ("idx_evidence_bookmarks_finding", ["finding_id"]),
        ("idx_evidence_bookmarks_report", ["report_id"]),
    ):
        op.create_index(name, "evidence_bookmarks", columns)


def _create_tags() -> None:
    op.create_table(
        "investigation_tags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column(
            "color",
            sa.String(length=20),
            server_default="slate",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_investigation_tags_name"),
    )
    op.create_index(
        "idx_investigation_tags_name",
        "investigation_tags",
        ["name"],
    )
    op.create_table(
        "investigation_tag_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
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
            ["tag_id"],
            ["investigation_tags.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "investigation_id",
            "tag_id",
            name="uq_investigation_tag_links_pair",
        ),
    )
    op.create_index(
        "idx_investigation_tag_links_investigation",
        "investigation_tag_links",
        ["investigation_id"],
    )
    op.create_index(
        "idx_investigation_tag_links_tag",
        "investigation_tag_links",
        ["tag_id"],
    )
    tag_table = sa.table(
        "investigation_tags",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String()),
        sa.column("color", sa.String()),
    )
    op.bulk_insert(
        tag_table,
        [
            {"id": uuid.UUID(tag_id), "name": name, "color": color}
            for tag_id, name, color in _DEFAULT_TAGS
        ],
    )
