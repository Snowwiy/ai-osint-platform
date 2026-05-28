"""phase1d findings engine

Revision ID: 0004_phase1d_findings
Revises: 0003_phase1b_threat_findings
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_phase1d_findings"
down_revision: Union[str, None] = "0003_phase1b_threat_findings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "findings",
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("findings", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("findings", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "findings",
        sa.Column(
            "severity",
            sa.String(length=20),
            server_default="info",
            nullable=False,
        ),
    )
    op.add_column(
        "findings",
        sa.Column(
            "confidence_score",
            sa.SmallInteger(),
            server_default="50",
            nullable=False,
        ),
    )
    op.add_column(
        "findings",
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="open",
            nullable=False,
        ),
    )
    op.add_column(
        "findings",
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "findings",
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.execute(
        """
        UPDATE findings
        SET investigation_id = targets.investigation_id
        FROM targets
        WHERE findings.target_id = targets.id
        """
    )
    op.execute(
        """
        UPDATE findings
        SET title = COALESCE(source, 'Legacy finding'),
            description = 'Legacy Phase 0 finding migrated to normalized findings.'
        WHERE title IS NULL
        """
    )

    op.alter_column("findings", "investigation_id", nullable=False)
    op.alter_column("findings", "title", nullable=False)
    op.alter_column("findings", "description", nullable=False)
    op.alter_column("findings", "target_id", nullable=True)
    op.alter_column(
        "findings",
        "raw_data",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        existing_nullable=False,
    )
    op.alter_column(
        "findings",
        "normalized_data",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        existing_nullable=False,
    )

    op.create_foreign_key(
        "fk_findings_investigation_id_investigations",
        "findings",
        "investigations",
        ["investigation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_findings_created_by_users",
        "findings",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_findings_confidence_score",
        "findings",
        "confidence_score BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_findings_severity",
        "findings",
        "severity IN ('info', 'low', 'medium', 'high', 'critical')",
    )
    op.create_check_constraint(
        "ck_findings_status",
        "findings",
        "status IN ('open', 'validated', 'false_positive', 'resolved')",
    )
    op.create_index("idx_findings_investigation", "findings", ["investigation_id"])
    op.create_index("idx_findings_severity", "findings", ["severity"])
    op.create_index("idx_findings_status", "findings", ["status"])

    op.create_table(
        "finding_evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recon_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("threat_finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "data",
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
            ["finding_id"],
            ["findings.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recon_entity_id"],
            ["recon_entities.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["threat_finding_id"],
            ["threat_findings.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_finding_evidence_finding",
        "finding_evidence",
        ["finding_id"],
    )
    op.create_index(
        "idx_finding_evidence_recon_entity",
        "finding_evidence",
        ["recon_entity_id"],
    )
    op.create_index(
        "idx_finding_evidence_threat_finding",
        "finding_evidence",
        ["threat_finding_id"],
    )

    op.create_table(
        "finding_tags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("finding_id", "tag", name="uq_finding_tags_finding_tag"),
    )
    op.create_index("idx_finding_tags_finding", "finding_tags", ["finding_id"])
    op.create_index("idx_finding_tags_tag", "finding_tags", ["tag"])


def downgrade() -> None:
    op.drop_index("idx_finding_tags_tag", table_name="finding_tags")
    op.drop_index("idx_finding_tags_finding", table_name="finding_tags")
    op.drop_table("finding_tags")

    op.drop_index(
        "idx_finding_evidence_threat_finding",
        table_name="finding_evidence",
    )
    op.drop_index(
        "idx_finding_evidence_recon_entity",
        table_name="finding_evidence",
    )
    op.drop_index("idx_finding_evidence_finding", table_name="finding_evidence")
    op.drop_table("finding_evidence")

    op.drop_index("idx_findings_status", table_name="findings")
    op.drop_index("idx_findings_severity", table_name="findings")
    op.drop_index("idx_findings_investigation", table_name="findings")
    op.drop_constraint("ck_findings_status", "findings", type_="check")
    op.drop_constraint("ck_findings_severity", "findings", type_="check")
    op.drop_constraint("ck_findings_confidence_score", "findings", type_="check")
    op.drop_constraint("fk_findings_created_by_users", "findings", type_="foreignkey")
    op.drop_constraint(
        "fk_findings_investigation_id_investigations",
        "findings",
        type_="foreignkey",
    )
    op.alter_column("findings", "target_id", nullable=False)
    op.alter_column(
        "findings",
        "normalized_data",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "findings",
        "raw_data",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=None,
        existing_nullable=False,
    )
    op.drop_column("findings", "updated_at")
    op.drop_column("findings", "created_at")
    op.drop_column("findings", "created_by")
    op.drop_column("findings", "status")
    op.drop_column("findings", "confidence_score")
    op.drop_column("findings", "severity")
    op.drop_column("findings", "description")
    op.drop_column("findings", "title")
    op.drop_column("findings", "investigation_id")
