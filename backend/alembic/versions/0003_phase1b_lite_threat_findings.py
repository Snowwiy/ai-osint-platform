"""phase1b lite threat findings

Revision ID: 0003_phase1b_threat_findings
Revises: 0002_phase1a_recon_entities
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase1b_threat_findings"
down_revision: Union[str, None] = "0002_phase1a_recon_entities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "threat_findings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recon_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_value", sa.String(length=500), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("risk_score", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column(
            "confidence", sa.String(length=10), server_default="low", nullable=False
        ),
        sa.Column("verdict", sa.String(length=30), nullable=False),
        sa.Column(
            "signals",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "normalized_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "raw_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "collected_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "target_type IN ('domain', 'ip', 'url')",
            name="ck_threat_findings_target_type",
        ),
        sa.CheckConstraint(
            "provider IN ('abuseipdb', 'virustotal')",
            name="ck_threat_findings_provider",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'completed', 'provider_unavailable', 'skipped', "
            "'failed', 'rate_limited'"
            ")",
            name="ck_threat_findings_status",
        ),
        sa.CheckConstraint(
            "risk_score BETWEEN 0 AND 100",
            name="ck_threat_risk_score",
        ),
        sa.CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_threat_findings_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recon_entity_id"],
            ["recon_entities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_threat_findings_investigation",
        "threat_findings",
        ["investigation_id"],
    )
    op.create_index(
        "idx_threat_findings_entity",
        "threat_findings",
        ["recon_entity_id"],
    )
    op.create_index("idx_threat_findings_provider", "threat_findings", ["provider"])
    op.create_index(
        "idx_threat_findings_risk_score",
        "threat_findings",
        [sa.text("risk_score DESC")],
    )
    op.create_index(
        "idx_threat_findings_collected",
        "threat_findings",
        [sa.text("collected_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_threat_findings_collected", table_name="threat_findings")
    op.drop_index("idx_threat_findings_risk_score", table_name="threat_findings")
    op.drop_index("idx_threat_findings_provider", table_name="threat_findings")
    op.drop_index("idx_threat_findings_entity", table_name="threat_findings")
    op.drop_index("idx_threat_findings_investigation", table_name="threat_findings")
    op.drop_table("threat_findings")
