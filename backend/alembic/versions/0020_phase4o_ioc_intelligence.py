"""Add reusable IOC intelligence and investigation observations.

Revision ID: 0020_phase4o_ioc_intelligence
Revises: 0019_phase4l_workspace
Create Date: 2026-06-15

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_phase4o_ioc_intelligence"
down_revision: str | None = "0019_phase4l_workspace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "iocs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("value", sa.String(length=1000), nullable=False),
        sa.Column("normalized_value", sa.String(length=1000), nullable=False),
        sa.Column("ioc_type", sa.String(length=20), nullable=False),
        sa.Column(
            "source",
            sa.String(length=100),
            server_default="passive_recon",
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.String(length=10),
            server_default="low",
            nullable=False,
        ),
        sa.Column(
            "confidence_reason",
            sa.Text(),
            server_default="A single passive observation is available.",
            nullable=False,
        ),
        sa.Column(
            "first_seen",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ioc_type IN ("
            "'ip', 'domain', 'subdomain', 'url', 'email', 'hash', "
            "'asn', 'certificate', 'hostname', 'technology'"
            ")",
            name="ck_iocs_type",
        ),
        sa.CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_iocs_confidence",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ioc_type",
            "normalized_value",
            name="uq_iocs_type_normalized_value",
        ),
    )
    op.create_index("idx_iocs_type", "iocs", ["ioc_type"])
    op.create_index(
        "idx_iocs_normalized_value",
        "iocs",
        ["normalized_value"],
    )
    op.create_index("idx_iocs_confidence", "iocs", ["confidence"])
    op.create_index(
        "idx_iocs_last_seen",
        "iocs",
        [sa.text("last_seen DESC")],
    )

    op.create_table(
        "ioc_observations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("ioc_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "investigation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "recon_entity_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column(
            "observation_count",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "evidence_quality",
            sa.SmallInteger(),
            server_default="50",
            nullable=False,
        ),
        sa.Column(
            "first_seen",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "observation_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "evidence_quality BETWEEN 0 AND 100",
            name="ck_ioc_observations_evidence_quality",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ioc_id"],
            ["iocs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recon_entity_id"],
            ["recon_entities.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ioc_id",
            "investigation_id",
            name="uq_ioc_observations_ioc_investigation",
        ),
        sa.UniqueConstraint(
            "recon_entity_id",
            name="uq_ioc_observations_recon_entity",
        ),
    )
    op.create_index(
        "idx_ioc_observations_ioc",
        "ioc_observations",
        ["ioc_id"],
    )
    op.create_index(
        "idx_ioc_observations_investigation",
        "ioc_observations",
        ["investigation_id"],
    )
    op.create_index(
        "idx_ioc_observations_entity",
        "ioc_observations",
        ["recon_entity_id"],
    )
    op.create_index(
        "idx_ioc_observations_last_seen",
        "ioc_observations",
        [sa.text("last_seen DESC")],
    )

    op.execute(
        """
        INSERT INTO iocs (
            value,
            normalized_value,
            ioc_type,
            source,
            first_seen,
            last_seen,
            tags
        )
        SELECT
            min(value),
            lower(trim(value)),
            CASE entity_type
                WHEN 'Domain' THEN 'domain'
                WHEN 'Subdomain' THEN 'subdomain'
                WHEN 'IPAddress' THEN 'ip'
                WHEN 'ASN' THEN 'asn'
                WHEN 'Certificate' THEN 'certificate'
                WHEN 'Technology' THEN 'technology'
                WHEN 'Service' THEN
                    CASE
                        WHEN value ~* '^https?://' THEN 'url'
                        ELSE 'hostname'
                    END
            END,
            coalesce(min(source), 'passive_recon'),
            min(first_seen),
            max(last_seen),
            ARRAY[
                lower(min(entity_type)),
                coalesce(min(source), 'passive_recon')
            ]::text[]
        FROM recon_entities
        WHERE entity_type IN (
            'Domain',
            'Subdomain',
            'IPAddress',
            'ASN',
            'Certificate',
            'Technology',
            'Service'
        )
        GROUP BY
            lower(trim(value)),
            CASE entity_type
                WHEN 'Domain' THEN 'domain'
                WHEN 'Subdomain' THEN 'subdomain'
                WHEN 'IPAddress' THEN 'ip'
                WHEN 'ASN' THEN 'asn'
                WHEN 'Certificate' THEN 'certificate'
                WHEN 'Technology' THEN 'technology'
                WHEN 'Service' THEN
                    CASE
                        WHEN value ~* '^https?://' THEN 'url'
                        ELSE 'hostname'
                    END
            END
        ON CONFLICT (ioc_type, normalized_value) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO ioc_observations (
            ioc_id,
            investigation_id,
            recon_entity_id,
            source,
            evidence_quality,
            first_seen,
            last_seen,
            observation_metadata
        )
        SELECT
            i.id,
            r.investigation_id,
            r.id,
            coalesce(r.source, 'passive_recon'),
            CASE
                WHEN r.properties <> '{}'::jsonb AND r.source IS NOT NULL THEN 80
                WHEN r.properties <> '{}'::jsonb THEN 65
                ELSE 50
            END,
            r.first_seen,
            r.last_seen,
            jsonb_build_object(
                'entity_type', r.entity_type,
                'display_name', r.display_name
            )
        FROM recon_entities r
        JOIN iocs i
          ON i.normalized_value = lower(trim(r.value))
         AND i.ioc_type = CASE r.entity_type
            WHEN 'Domain' THEN 'domain'
            WHEN 'Subdomain' THEN 'subdomain'
            WHEN 'IPAddress' THEN 'ip'
            WHEN 'ASN' THEN 'asn'
            WHEN 'Certificate' THEN 'certificate'
            WHEN 'Technology' THEN 'technology'
            WHEN 'Service' THEN
                CASE
                    WHEN r.value ~* '^https?://' THEN 'url'
                    ELSE 'hostname'
                END
         END
        WHERE r.entity_type IN (
            'Domain',
            'Subdomain',
            'IPAddress',
            'ASN',
            'Certificate',
            'Technology',
            'Service'
        )
        ON CONFLICT (ioc_id, investigation_id) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE iocs i
        SET
            confidence = CASE
                WHEN counts.investigation_count >= 3 THEN 'high'
                WHEN counts.investigation_count = 2 THEN 'medium'
                ELSE 'low'
            END,
            confidence_reason = CASE
                WHEN counts.investigation_count >= 3
                    THEN 'Observed in three or more investigations.'
                WHEN counts.investigation_count = 2
                    THEN 'Observed in two investigations.'
                ELSE 'A single passive observation is available.'
            END
        FROM (
            SELECT ioc_id, count(*) AS investigation_count
            FROM ioc_observations
            GROUP BY ioc_id
        ) counts
        WHERE i.id = counts.ioc_id
        """
    )


def downgrade() -> None:
    op.drop_index(
        "idx_ioc_observations_last_seen",
        table_name="ioc_observations",
    )
    op.drop_index(
        "idx_ioc_observations_entity",
        table_name="ioc_observations",
    )
    op.drop_index(
        "idx_ioc_observations_investigation",
        table_name="ioc_observations",
    )
    op.drop_index(
        "idx_ioc_observations_ioc",
        table_name="ioc_observations",
    )
    op.drop_table("ioc_observations")
    op.drop_index("idx_iocs_last_seen", table_name="iocs")
    op.drop_index("idx_iocs_confidence", table_name="iocs")
    op.drop_index("idx_iocs_normalized_value", table_name="iocs")
    op.drop_index("idx_iocs_type", table_name="iocs")
    op.drop_table("iocs")
