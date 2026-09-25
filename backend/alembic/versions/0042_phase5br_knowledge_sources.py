"""Add managed local Knowledge sources, provenance, and explicit links.

Revision ID: 0042_phase5br_knowledge_sources
Revises: 0041_phase5bq_lan_discovery
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042_phase5br_knowledge_sources"
down_revision: str | None = "0041_phase5bq_lan_discovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("root_path", sa.Text(), nullable=True),
        sa.Column("local_root_path", sa.Text(), nullable=True),
        sa.Column("display_location", sa.String(500), nullable=False),
        sa.Column("category", sa.String(80), server_default="Other", nullable=False),
        sa.Column("platform", sa.String(20), nullable=True),
        sa.Column(
            "availability", sa.String(20), server_default="available", nullable=False
        ),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column(
            "trust_level", sa.String(24), server_default="unknown", nullable=False
        ),
        sa.Column(
            "verification_status",
            sa.String(24),
            server_default="unverified",
            nullable=False,
        ),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("publisher", sa.String(200), nullable=True),
        sa.Column("canonical_url", sa.String(1000), nullable=True),
        sa.Column("publication_date", sa.String(40), nullable=True),
        sa.Column("version_label", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "last_indexed_at", postgresql.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("last_seen_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("document_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", sa.String(255), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_knowledge_sources_status", "knowledge_sources", ["status"])
    op.create_index(
        "idx_knowledge_sources_trust",
        "knowledge_sources",
        ["trust_level", "verification_status"],
    )
    op.drop_index("idx_knowledge_documents_hash", table_name="knowledge_documents")
    op.create_index(
        "idx_knowledge_documents_hash", "knowledge_documents", ["hash"], unique=False
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("relative_name", sa.String(1000), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("category", sa.String(80), server_default="Other", nullable=False),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "content_type",
            sa.String(80),
            server_default="text/markdown",
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_documents", sa.Column("language", sa.String(16), nullable=True)
    )
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "trust_level", sa.String(24), server_default="unknown", nullable=False
        ),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "verification_status",
            sa.String(24),
            server_default="unverified",
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "document_status", sa.String(32), server_default="ready", nullable=False
        ),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("size_bytes", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("indexed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_knowledge_documents_source",
        "knowledge_documents",
        "knowledge_sources",
        ["source_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_knowledge_documents_source", "knowledge_documents", ["source_id"]
    )
    op.create_index(
        "idx_knowledge_documents_verification",
        "knowledge_documents",
        ["trust_level", "verification_status"],
    )
    op.create_index(
        "idx_knowledge_documents_category", "knowledge_documents", ["category"]
    )
    op.create_table(
        "knowledge_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_name", sa.String(500), nullable=False),
        sa.Column("link_alias", sa.String(500), nullable=True),
        sa.Column(
            "link_kind", sa.String(16), server_default="wikilink", nullable=False
        ),
        sa.Column(
            "resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["knowledge_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_document_id"], ["knowledge_documents.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_document_id",
            "target_name",
            "link_kind",
            name="uq_knowledge_links_target",
        ),
    )
    op.create_index(
        "idx_knowledge_links_source", "knowledge_links", ["source_document_id"]
    )
    op.create_index(
        "idx_knowledge_links_target", "knowledge_links", ["target_document_id"]
    )


def downgrade() -> None:
    duplicate_hash = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT hash FROM knowledge_documents GROUP BY hash "
                "HAVING COUNT(*) > 1 LIMIT 1"
            )
        )
        .first()
    )
    if duplicate_hash is not None:
        raise RuntimeError(
            "Cannot restore the legacy unique Knowledge hash index while "
            "duplicate documents exist."
        )
    op.drop_index("idx_knowledge_links_target", table_name="knowledge_links")
    op.drop_index("idx_knowledge_links_source", table_name="knowledge_links")
    op.drop_table("knowledge_links")
    op.drop_index(
        "idx_knowledge_documents_verification", table_name="knowledge_documents"
    )
    op.drop_index("idx_knowledge_documents_source", table_name="knowledge_documents")
    op.drop_constraint(
        "fk_knowledge_documents_source", "knowledge_documents", type_="foreignkey"
    )
    op.drop_index("idx_knowledge_documents_category", table_name="knowledge_documents")
    for column in (
        "metadata",
        "indexed_at",
        "size_bytes",
        "document_status",
        "verification_status",
        "trust_level",
        "language",
        "content_type",
        "category",
        "relative_name",
        "source_id",
    ):
        op.drop_column("knowledge_documents", column)
    op.drop_index("idx_knowledge_documents_hash", table_name="knowledge_documents")
    op.create_index(
        "idx_knowledge_documents_hash", "knowledge_documents", ["hash"], unique=True
    )
    op.drop_index("idx_knowledge_sources_trust", table_name="knowledge_sources")
    op.drop_index("idx_knowledge_sources_status", table_name="knowledge_sources")
    op.drop_column("knowledge_sources", "content_hash")
    op.drop_column("knowledge_sources", "category")
    op.drop_table("knowledge_sources")
