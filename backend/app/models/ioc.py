from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IOC(Base):
    __tablename__ = "iocs"
    __table_args__ = (
        CheckConstraint(
            "ioc_type IN ("
            "'ip', 'domain', 'subdomain', 'url', 'email', 'hash', "
            "'asn', 'certificate', 'hostname', 'technology'"
            ")",
            name="ck_iocs_type",
        ),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_iocs_confidence",
        ),
        UniqueConstraint(
            "ioc_type",
            "normalized_value",
            name="uq_iocs_type_normalized_value",
        ),
        Index("idx_iocs_type", "ioc_type"),
        Index("idx_iocs_normalized_value", "normalized_value"),
        Index("idx_iocs_confidence", "confidence"),
        Index("idx_iocs_last_seen", text("last_seen DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    value: Mapped[str] = mapped_column(String(1000), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(1000), nullable=False)
    ioc_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="passive_recon",
        server_default="passive_recon",
    )
    confidence: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="low",
        server_default="low",
    )
    confidence_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="A single passive observation is available.",
        server_default="A single passive observation is available.",
    )
    first_seen: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class IOCObservation(Base):
    __tablename__ = "ioc_observations"
    __table_args__ = (
        CheckConstraint(
            "evidence_quality BETWEEN 0 AND 100",
            name="ck_ioc_observations_evidence_quality",
        ),
        UniqueConstraint(
            "ioc_id",
            "investigation_id",
            name="uq_ioc_observations_ioc_investigation",
        ),
        UniqueConstraint(
            "recon_entity_id",
            name="uq_ioc_observations_recon_entity",
        ),
        Index("idx_ioc_observations_ioc", "ioc_id"),
        Index("idx_ioc_observations_investigation", "investigation_id"),
        Index("idx_ioc_observations_entity", "recon_entity_id"),
        Index("idx_ioc_observations_last_seen", text("last_seen DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    ioc_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("iocs.id", ondelete="CASCADE"),
        nullable=False,
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    recon_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recon_entities.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    evidence_quality: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=50,
        server_default="50",
    )
    first_seen: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    observation_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
