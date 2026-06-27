from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
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


class ThreatCampaign(Base):
    __tablename__ = "threat_campaigns"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'monitoring', 'closed', 'archived')",
            name="ck_threat_campaigns_status",
        ),
        CheckConstraint(
            "confidence IN ('Low', 'Medium', 'High', 'Confirmed')",
            name="ck_threat_campaigns_confidence",
        ),
        Index("idx_threat_campaigns_status", "status"),
        Index("idx_threat_campaigns_confidence", "confidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="monitoring",
        server_default="monitoring",
    )
    confidence: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Low",
        server_default="Low",
    )
    first_observed: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    last_observed: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    campaign_metadata: Mapped[dict[str, Any]] = mapped_column(
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


class ThreatGroup(Base):
    __tablename__ = "threat_groups"
    __table_args__ = (
        CheckConstraint(
            "confidence IN ('Low', 'Medium', 'High', 'Confirmed')",
            name="ck_threat_groups_confidence",
        ),
        Index("idx_threat_groups_confidence", "confidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Low",
        server_default="Low",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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


class ThreatTechnique(Base):
    __tablename__ = "threat_techniques"
    __table_args__ = (
        Index("idx_threat_techniques_technique_id", "technique_id"),
        Index("idx_threat_techniques_tactic", "tactic"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    technique_id: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tactic: Mapped[str | None] = mapped_column(String(120), nullable=True)
    procedure: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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


class ThreatCampaignIndicator(Base):
    __tablename__ = "threat_campaign_indicators"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "ioc_id",
            name="uq_threat_campaign_indicators_pair",
        ),
        Index("idx_threat_campaign_indicators_campaign_id", "campaign_id"),
        Index("idx_threat_campaign_indicators_ioc_id", "ioc_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("threat_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    ioc_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("iocs.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ThreatCampaignFinding(Base):
    __tablename__ = "threat_campaign_findings"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "finding_id",
            name="uq_threat_campaign_findings_pair",
        ),
        Index("idx_threat_campaign_findings_campaign_id", "campaign_id"),
        Index("idx_threat_campaign_findings_finding_id", "finding_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("threat_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ThreatCampaignInvestigation(Base):
    __tablename__ = "threat_campaign_investigations"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "investigation_id",
            name="uq_threat_campaign_investigations_pair",
        ),
        Index("idx_threat_campaign_investigations_campaign_id", "campaign_id"),
        Index(
            "idx_threat_campaign_investigations_investigation_id",
            "investigation_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("threat_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ThreatCampaignTechnique(Base):
    __tablename__ = "threat_campaign_techniques"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "technique_id",
            name="uq_threat_campaign_techniques_pair",
        ),
        Index("idx_threat_campaign_techniques_campaign_id", "campaign_id"),
        Index("idx_threat_campaign_techniques_technique_id", "technique_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("threat_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    technique_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("threat_techniques.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ThreatGroupCampaign(Base):
    __tablename__ = "threat_group_campaigns"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "campaign_id",
            name="uq_threat_group_campaigns_pair",
        ),
        Index("idx_threat_group_campaigns_group_id", "group_id"),
        Index("idx_threat_group_campaigns_campaign_id", "campaign_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("threat_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("threat_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ThreatGroupIndicator(Base):
    __tablename__ = "threat_group_indicators"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "ioc_id",
            name="uq_threat_group_indicators_pair",
        ),
        Index("idx_threat_group_indicators_group_id", "group_id"),
        Index("idx_threat_group_indicators_ioc_id", "ioc_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("threat_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    ioc_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("iocs.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ThreatGroupTechnique(Base):
    __tablename__ = "threat_group_techniques"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "technique_id",
            name="uq_threat_group_techniques_pair",
        ),
        Index("idx_threat_group_techniques_group_id", "group_id"),
        Index("idx_threat_group_techniques_technique_id", "technique_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("threat_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    technique_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("threat_techniques.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ThreatFindingTechnique(Base):
    __tablename__ = "threat_finding_techniques"
    __table_args__ = (
        Index("idx_threat_finding_techniques_finding", "finding_id"),
        Index("idx_threat_finding_techniques_technique", "technique_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
    )
    technique_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("threat_techniques.id", ondelete="CASCADE"),
        nullable=False,
    )
    mapped_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
