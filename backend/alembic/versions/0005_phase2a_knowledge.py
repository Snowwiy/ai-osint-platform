"""phase2a knowledge base

Revision ID: 0005_phase2a_knowledge
Revises: 0004_phase1d_findings
Create Date: 2026-05-28

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_phase2a_knowledge"
down_revision: Union[str, None] = "0004_phase1d_findings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
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
            "source_type IN ("
            "'security_notes', 'frameworks', 'playbooks', 'osint_notes'"
            ")",
            name="ck_knowledge_documents_source_type",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_knowledge_documents_source_type",
        "knowledge_documents",
        ["source_type"],
    )
    op.create_index(
        "idx_knowledge_documents_hash",
        "knowledge_documents",
        ["hash"],
        unique=True,
    )
    op.create_index(
        "idx_knowledge_documents_file_path",
        "knowledge_documents",
        ["file_path"],
        unique=True,
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column(
            "embedding_metadata",
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
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["knowledge_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_knowledge_chunks_document_index",
        ),
    )
    op.create_index(
        "idx_knowledge_chunks_document",
        "knowledge_chunks",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_chunks_document", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index(
        "idx_knowledge_documents_file_path",
        table_name="knowledge_documents",
    )
    op.drop_index("idx_knowledge_documents_hash", table_name="knowledge_documents")
    op.drop_index(
        "idx_knowledge_documents_source_type",
        table_name="knowledge_documents",
    )
    op.drop_table("knowledge_documents")
