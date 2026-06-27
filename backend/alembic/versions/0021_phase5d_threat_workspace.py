"""Add defensive threat intelligence workspace tables.

Revision ID: 0021_phase5d_threat_workspace
Revises: 0020_phase4o_ioc_intelligence
Create Date: 2026-06-24

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_phase5d_threat_workspace"
down_revision: str | None = "0020_phase4o_ioc_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        postgresql.TIMESTAMP(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "threat_campaigns",
        _uuid_pk(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="monitoring",
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.String(length=20),
            server_default="Low",
            nullable=False,
        ),
        sa.Column(
            "first_observed",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_observed",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "campaign_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        _created_at(),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'monitoring', 'closed', 'archived')",
            name="ck_threat_campaigns_status",
        ),
        sa.CheckConstraint(
            "confidence IN ('Low', 'Medium', 'High', 'Confirmed')",
            name="ck_threat_campaigns_confidence",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_threat_campaigns_status", "threat_campaigns", ["status"])
    op.create_index(
        "idx_threat_campaigns_confidence",
        "threat_campaigns",
        ["confidence"],
    )

    op.create_table(
        "threat_groups",
        _uuid_pk(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "confidence",
            sa.String(length=20),
            server_default="Low",
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        _created_at(),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence IN ('Low', 'Medium', 'High', 'Confirmed')",
            name="ck_threat_groups_confidence",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_threat_groups_confidence",
        "threat_groups",
        ["confidence"],
    )

    op.create_table(
        "threat_techniques",
        _uuid_pk(),
        sa.Column("technique_id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("tactic", sa.String(length=120), nullable=True),
        sa.Column("procedure", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        _created_at(),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_threat_techniques_technique_id",
        "threat_techniques",
        ["technique_id"],
    )
    op.create_index("idx_threat_techniques_tactic", "threat_techniques", ["tactic"])

    _create_link_table(
        "threat_campaign_indicators",
        "campaign_id",
        "threat_campaigns.id",
        "ioc_id",
        "iocs.id",
    )
    _create_link_table(
        "threat_campaign_findings",
        "campaign_id",
        "threat_campaigns.id",
        "finding_id",
        "findings.id",
    )
    _create_link_table(
        "threat_campaign_investigations",
        "campaign_id",
        "threat_campaigns.id",
        "investigation_id",
        "investigations.id",
    )
    _create_link_table(
        "threat_campaign_techniques",
        "campaign_id",
        "threat_campaigns.id",
        "technique_id",
        "threat_techniques.id",
    )
    _create_link_table(
        "threat_group_campaigns",
        "group_id",
        "threat_groups.id",
        "campaign_id",
        "threat_campaigns.id",
    )
    _create_link_table(
        "threat_group_indicators",
        "group_id",
        "threat_groups.id",
        "ioc_id",
        "iocs.id",
    )
    _create_link_table(
        "threat_group_techniques",
        "group_id",
        "threat_groups.id",
        "technique_id",
        "threat_techniques.id",
    )

    op.create_table(
        "threat_finding_techniques",
        _uuid_pk(),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("technique_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mapped_by", postgresql.UUID(as_uuid=True), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["technique_id"],
            ["threat_techniques.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["mapped_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_threat_finding_techniques_finding",
        "threat_finding_techniques",
        ["finding_id"],
    )
    op.create_index(
        "idx_threat_finding_techniques_technique",
        "threat_finding_techniques",
        ["technique_id"],
    )


def downgrade() -> None:
    for table_name in (
        "threat_finding_techniques",
        "threat_group_techniques",
        "threat_group_indicators",
        "threat_group_campaigns",
        "threat_campaign_techniques",
        "threat_campaign_investigations",
        "threat_campaign_findings",
        "threat_campaign_indicators",
        "threat_techniques",
        "threat_groups",
        "threat_campaigns",
    ):
        op.drop_table(table_name)


def _create_link_table(
    table_name: str,
    left_name: str,
    left_target: str,
    right_name: str,
    right_target: str,
) -> None:
    op.create_table(
        table_name,
        _uuid_pk(),
        sa.Column(left_name, postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(right_name, postgresql.UUID(as_uuid=True), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint([left_name], [left_target], ondelete="CASCADE"),
        sa.ForeignKeyConstraint([right_name], [right_target], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(left_name, right_name, name=f"uq_{table_name}_pair"),
    )
    op.create_index(f"idx_{table_name}_{left_name}", table_name, [left_name])
    op.create_index(f"idx_{table_name}_{right_name}", table_name, [right_name])
