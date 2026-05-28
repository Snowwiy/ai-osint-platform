"""phase1a recon entities

Revision ID: 0002_phase1a_recon_entities
Revises: 0001_initial
Create Date: 2026-05-27

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase1a_recon_entities"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recon_entities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("display_name", sa.String(length=500), nullable=True),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column(
            "first_seen",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "entity_type IN ("
            "'Domain', 'Subdomain', 'IPAddress', 'ASN', 'Certificate', "
            "'Organization', 'Service', 'Technology'"
            ")",
            name="ck_recon_entities_type",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "investigation_id",
            "entity_type",
            "value",
            name="uq_recon_entities_investigation_type_value",
        ),
    )
    op.create_index(
        "idx_recon_entities_investigation",
        "recon_entities",
        ["investigation_id"],
    )
    op.create_index("idx_recon_entities_type", "recon_entities", ["entity_type"])
    op.create_index("idx_recon_entities_value", "recon_entities", ["value"])

    op.create_table(
        "recon_relationships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "relationship_type IN ("
            "'RESOLVES_TO', 'BELONGS_TO', 'USES_CERTIFICATE', 'HOSTS', "
            "'RELATED_TO', 'DISCOVERED_FROM'"
            ")",
            name="ck_recon_relationships_type",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_id"],
            ["recon_entities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["recon_entities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "investigation_id",
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            name="uq_recon_relationships_unique_edge",
        ),
    )
    op.create_index(
        "idx_recon_relationships_investigation",
        "recon_relationships",
        ["investigation_id"],
    )
    op.create_index(
        "idx_recon_relationships_source",
        "recon_relationships",
        ["source_entity_id"],
    )
    op.create_index(
        "idx_recon_relationships_target",
        "recon_relationships",
        ["target_entity_id"],
    )
    op.create_index(
        "idx_recon_relationships_type",
        "recon_relationships",
        ["relationship_type"],
    )

    op.create_table(
        "investigation_enrichments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("initiated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_value", sa.String(length=500), nullable=False),
        sa.Column("authorization_statement", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "target_type IN ('domain', 'ip', 'url')",
            name="ck_investigation_enrichments_target_type",
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'partial', 'failed')",
            name="ck_investigation_enrichments_status",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["initiated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_investigation_enrichments_investigation",
        "investigation_enrichments",
        ["investigation_id"],
    )
    op.create_index(
        "idx_investigation_enrichments_target",
        "investigation_enrichments",
        ["target_type", "target_value"],
    )
    op.create_index(
        "idx_investigation_enrichments_created",
        "investigation_enrichments",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_investigation_enrichments_created",
        table_name="investigation_enrichments",
    )
    op.drop_index(
        "idx_investigation_enrichments_target",
        table_name="investigation_enrichments",
    )
    op.drop_index(
        "idx_investigation_enrichments_investigation",
        table_name="investigation_enrichments",
    )
    op.drop_table("investigation_enrichments")

    op.drop_index("idx_recon_relationships_type", table_name="recon_relationships")
    op.drop_index("idx_recon_relationships_target", table_name="recon_relationships")
    op.drop_index("idx_recon_relationships_source", table_name="recon_relationships")
    op.drop_index(
        "idx_recon_relationships_investigation",
        table_name="recon_relationships",
    )
    op.drop_table("recon_relationships")

    op.drop_index("idx_recon_entities_value", table_name="recon_entities")
    op.drop_index("idx_recon_entities_type", table_name="recon_entities")
    op.drop_index("idx_recon_entities_investigation", table_name="recon_entities")
    op.drop_table("recon_entities")
