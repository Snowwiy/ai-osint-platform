from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case_closure import (
    CaseClosure,
    CaseClosureChecklistItem,
    CaseDeliverable,
)
from app.models.engagement import (
    AuthorizationEvidence,
    Engagement,
    EngagementScopeItem,
)
from app.models.evidence_bookmark import EvidenceBookmark
from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.investigation import Investigation
from app.models.investigation_evidence import InvestigationEvidence
from app.models.investigation_member import InvestigationMember
from app.models.investigation_note import InvestigationNote
from app.models.investigation_task import InvestigationTask
from app.models.investigation_workflow_event import InvestigationWorkflowEvent
from app.models.ioc import IOC, IOCObservation
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.models.playbook import PlaybookRun, PlaybookRunStep
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.report import Report
from app.models.target import Target
from app.models.threat_workspace import (
    ThreatCampaign,
    ThreatCampaignFinding,
    ThreatCampaignIndicator,
    ThreatCampaignInvestigation,
    ThreatCampaignTechnique,
    ThreatGroup,
    ThreatGroupCampaign,
    ThreatTechnique,
)
from app.models.user import User
from app.schemas.qa import DemoSeedResponse
from app.services.audit import record_event

DEMO_INVESTIGATION_ID = uuid.UUID("70000000-0000-4000-8000-000000000001")
DEMO_TARGET_ID = uuid.UUID("70000000-0000-4000-8000-000000000002")
DEMO_DOMAIN_ENTITY_ID = uuid.UUID("70000000-0000-4000-8000-000000000003")
DEMO_IP_ENTITY_ID = uuid.UUID("70000000-0000-4000-8000-000000000004")
DEMO_SERVICE_ENTITY_ID = uuid.UUID("70000000-0000-4000-8000-000000000005")
DEMO_TECH_ENTITY_ID = uuid.UUID("70000000-0000-4000-8000-000000000006")
DEMO_FINDING_ID = uuid.UUID("70000000-0000-4000-8000-000000000007")
DEMO_EVIDENCE_ID = uuid.UUID("70000000-0000-4000-8000-000000000008")
DEMO_TASK_ID = uuid.UUID("70000000-0000-4000-8000-000000000009")
DEMO_REPORT_ID = uuid.UUID("70000000-0000-4000-8000-000000000010")
DEMO_PLAYBOOK_RUN_ID = uuid.UUID("70000000-0000-4000-8000-000000000011")
DEMO_KNOWLEDGE_DOCUMENT_ID = uuid.UUID(
    "70000000-0000-4000-8000-000000000012"
)
DEMO_KNOWLEDGE_CHUNK_ID = uuid.UUID("70000000-0000-4000-8000-000000000013")
DEMO_WORKFLOW_EVENT_ID = uuid.UUID("70000000-0000-4000-8000-000000000014")
DEMO_NOTE_ID = uuid.UUID("70000000-0000-4000-8000-000000000015")
DEMO_INVESTIGATION_EVIDENCE_ID = uuid.UUID(
    "70000000-0000-4000-8000-000000000016"
)
DEMO_BOOKMARK_ID = uuid.UUID("70000000-0000-4000-8000-000000000017")
DEMO_IOC_ID = uuid.UUID("70000000-0000-4000-8000-000000000018")
DEMO_IOC_OBSERVATION_ID = uuid.UUID("70000000-0000-4000-8000-000000000019")
DEMO_CAMPAIGN_ID = uuid.UUID("70000000-0000-4000-8000-000000000020")
DEMO_TECHNIQUE_ID = uuid.UUID("70000000-0000-4000-8000-000000000021")
DEMO_GROUP_ID = uuid.UUID("70000000-0000-4000-8000-000000000022")
DEMO_CAMPAIGN_IOC_LINK_ID = uuid.UUID(
    "70000000-0000-4000-8000-000000000023"
)
DEMO_CAMPAIGN_FINDING_LINK_ID = uuid.UUID(
    "70000000-0000-4000-8000-000000000024"
)
DEMO_CAMPAIGN_INVESTIGATION_LINK_ID = uuid.UUID(
    "70000000-0000-4000-8000-000000000025"
)
DEMO_CAMPAIGN_TECHNIQUE_LINK_ID = uuid.UUID(
    "70000000-0000-4000-8000-000000000026"
)
DEMO_GROUP_CAMPAIGN_LINK_ID = uuid.UUID(
    "70000000-0000-4000-8000-000000000027"
)
DEMO_RELATIONSHIP_DOMAIN_IP_ID = uuid.UUID(
    "70000000-0000-4000-8000-000000000028"
)
DEMO_RELATIONSHIP_DOMAIN_SERVICE_ID = uuid.UUID(
    "70000000-0000-4000-8000-000000000029"
)
DEMO_RELATIONSHIP_SERVICE_TECH_ID = uuid.UUID(
    "70000000-0000-4000-8000-000000000030"
)
DEMO_ENGAGEMENT_ID = uuid.UUID("70000000-0000-4000-8000-000000000031")
DEMO_SCOPE_DOMAIN_ID = uuid.UUID("70000000-0000-4000-8000-000000000032")
DEMO_SCOPE_IP_ID = uuid.UUID("70000000-0000-4000-8000-000000000033")
DEMO_AUTH_EVIDENCE_ID = uuid.UUID("70000000-0000-4000-8000-000000000034")
DEMO_CLOSURE_ID = uuid.UUID("70000000-0000-4000-8000-000000000035")
DEMO_CLOSURE_CHECK_SCOPE_ID = uuid.UUID("70000000-0000-4000-8000-000000000036")
DEMO_CLOSURE_CHECK_REPORT_ID = uuid.UUID("70000000-0000-4000-8000-000000000037")
DEMO_EXEC_DELIVERABLE_ID = uuid.UUID("70000000-0000-4000-8000-000000000038")
DEMO_TECH_DELIVERABLE_ID = uuid.UUID("70000000-0000-4000-8000-000000000039")
DEMO_PACKAGE_DELIVERABLE_ID = uuid.UUID("70000000-0000-4000-8000-000000000040")

PUBLIC_EXPOSURE_PLAYBOOK_ID = uuid.UUID(
    "10000000-0000-4000-8000-000000000002"
)
PUBLIC_EXPOSURE_STEP_IDS = [
    uuid.UUID(f"20000000-0000-4000-8002-{index:012d}") for index in range(1, 5)
]


async def set_demo_workspace_enabled(
    db: AsyncSession,
    user: User,
    *,
    enabled: bool,
) -> DemoSeedResponse:
    investigation = await db.get(Investigation, DEMO_INVESTIGATION_ID)
    if not enabled:
        if investigation is not None and investigation.status != "archived":
            investigation.status = "archived"
            db.add(investigation)
            await record_event(
                db,
                action="demo.disabled",
                actor_id=user.id,
                resource_type="investigation",
                resource_id=investigation.id,
                investigation_id=investigation.id,
                metadata={"demo": True},
            )
        return DemoSeedResponse(
            enabled=False,
            ready=False,
            investigation_id=investigation.id if investigation else None,
            message="Demo workspace is disabled and hidden from active work.",
        )

    investigation = await ensure_demo_workspace(db, user)
    if investigation.status == "archived":
        investigation.status = "active"
        db.add(investigation)
    await record_event(
        db,
        action="demo.enabled",
        actor_id=user.id,
        resource_type="investigation",
        resource_id=investigation.id,
        investigation_id=investigation.id,
        metadata={"demo": True},
    )
    return DemoSeedResponse(
        enabled=True,
        ready=True,
        investigation_id=investigation.id,
        message="Defensive demo workspace is ready.",
    )


async def clear_demo_workspace(
    db: AsyncSession,
    user: User,
) -> DemoSeedResponse:
    await record_event(
        db,
        action="demo.cleared",
        actor_id=user.id,
        resource_type="investigation",
        resource_id=DEMO_INVESTIGATION_ID,
        investigation_id=None,
        metadata={"demo": True, "synthetic": True},
    )
    await _delete_demo_records(db)
    return DemoSeedResponse(
        enabled=False,
        ready=False,
        investigation_id=None,
        message="Synthetic demo workspace records were cleared.",
    )


async def ensure_demo_workspace(
    db: AsyncSession,
    user: User,
) -> Investigation:
    now = datetime.now(UTC)
    await _ensure_demo_engagement(db, user, now)
    investigation = await db.get(Investigation, DEMO_INVESTIGATION_ID)
    if investigation is None:
        investigation = Investigation(
            id=DEMO_INVESTIGATION_ID,
            title="[DEMO] Authorized External Exposure Review",
            description=(
                "Synthetic defensive case for product demonstrations. All assets "
                "use reserved example identifiers and do not represent a real "
                "organization or compromise."
            ),
            owner_id=user.id,
            engagement_id=DEMO_ENGAGEMENT_ID,
            status="active",
            stage="analysis",
            authorization_statement=(
                "This synthetic demonstration is authorized for internal product "
                "evaluation only. It uses reserved domains and documentation IP "
                "ranges, performs no live requests, and represents no real incident."
            ),
            scope_definition=(
                "Reserved domain demo.raventech.invalid and TEST-NET address "
                "192.0.2.10 only."
            ),
            priority="high",
            scope_review_status="in_scope",
            scope_notes=(
                "Synthetic demo engagement scope includes the reserved demo "
                "domain and TEST-NET address used by this case."
            ),
            business_impact=(
                "Demonstrates evidence review, remediation ownership, and reporting "
                "without making a compromise claim."
            ),
            due_date=(now + timedelta(days=14)).date(),
        )
        db.add(investigation)
        await db.flush()
    else:
        investigation.title = "[DEMO] Authorized External Exposure Review"
        investigation.description = (
            "Synthetic defensive assessment using reserved example identifiers. "
            "The case demonstrates potential exposure review, analyst validation, "
            "remediation ownership, and client-ready reporting without live access."
        )
        investigation.stage = "analysis"
        investigation.engagement_id = DEMO_ENGAGEMENT_ID
        investigation.scope_review_status = "in_scope"
        investigation.scope_notes = (
            "Synthetic demo engagement scope includes the reserved demo "
            "domain and TEST-NET address used by this case."
        )
        investigation.business_impact = (
            "The observed configuration may increase operational exposure if "
            "ownership and defensive controls are not documented. This synthetic "
            "case does not assert compromise."
        )
        db.add(investigation)

    await _ensure_member(db, user)
    await _ensure_target(db, user)
    await _ensure_recon_entities(db)
    await _ensure_recon_relationships(db)
    await _ensure_finding(db, user)
    await _ensure_note(db, user)
    await _ensure_task(db, user, now)
    await _ensure_evidence(db, user)
    await _ensure_bookmark(db, user)
    await _ensure_ioc(db, now)
    await _ensure_threat_intelligence(db, user, now)
    await _ensure_playbook_run(db, user)
    await _ensure_report(db, user, now)
    await _ensure_closure(db, user, now)
    await _ensure_knowledge(db)
    await _ensure_workflow_event(db, user)
    await db.flush()
    return investigation


async def _delete_demo_records(db: AsyncSession) -> None:
    await db.execute(
        delete(CaseDeliverable).where(
            CaseDeliverable.id.in_(
                [
                    DEMO_EXEC_DELIVERABLE_ID,
                    DEMO_TECH_DELIVERABLE_ID,
                    DEMO_PACKAGE_DELIVERABLE_ID,
                ]
            )
        )
    )
    await db.execute(
        delete(CaseClosureChecklistItem).where(
            CaseClosureChecklistItem.id.in_(
                [DEMO_CLOSURE_CHECK_SCOPE_ID, DEMO_CLOSURE_CHECK_REPORT_ID]
            )
        )
    )
    await db.execute(delete(CaseClosure).where(CaseClosure.id == DEMO_CLOSURE_ID))
    await db.execute(
        delete(AuthorizationEvidence).where(
            AuthorizationEvidence.id == DEMO_AUTH_EVIDENCE_ID
        )
    )
    await db.execute(
        delete(EngagementScopeItem).where(
            EngagementScopeItem.id.in_([DEMO_SCOPE_DOMAIN_ID, DEMO_SCOPE_IP_ID])
        )
    )
    await db.execute(
        delete(ThreatGroupCampaign).where(
            ThreatGroupCampaign.id == DEMO_GROUP_CAMPAIGN_LINK_ID
        )
    )
    await db.execute(
        delete(ThreatCampaignTechnique).where(
            ThreatCampaignTechnique.id == DEMO_CAMPAIGN_TECHNIQUE_LINK_ID
        )
    )
    await db.execute(
        delete(ThreatCampaignInvestigation).where(
            ThreatCampaignInvestigation.id == DEMO_CAMPAIGN_INVESTIGATION_LINK_ID
        )
    )
    await db.execute(
        delete(ThreatCampaignFinding).where(
            ThreatCampaignFinding.id == DEMO_CAMPAIGN_FINDING_LINK_ID
        )
    )
    await db.execute(
        delete(ThreatCampaignIndicator).where(
            ThreatCampaignIndicator.id == DEMO_CAMPAIGN_IOC_LINK_ID
        )
    )
    await db.execute(delete(ThreatGroup).where(ThreatGroup.id == DEMO_GROUP_ID))
    await db.execute(
        delete(ThreatTechnique).where(ThreatTechnique.id == DEMO_TECHNIQUE_ID)
    )
    await db.execute(
        delete(ThreatCampaign).where(ThreatCampaign.id == DEMO_CAMPAIGN_ID)
    )
    await db.execute(
        delete(IOCObservation).where(IOCObservation.id == DEMO_IOC_OBSERVATION_ID)
    )
    await db.execute(delete(IOC).where(IOC.id == DEMO_IOC_ID))
    await db.execute(
        delete(KnowledgeChunk).where(KnowledgeChunk.id == DEMO_KNOWLEDGE_CHUNK_ID)
    )
    await db.execute(
        delete(KnowledgeDocument).where(
            KnowledgeDocument.id == DEMO_KNOWLEDGE_DOCUMENT_ID
        )
    )
    await db.execute(
        delete(Investigation).where(Investigation.id == DEMO_INVESTIGATION_ID)
    )
    await db.execute(delete(Engagement).where(Engagement.id == DEMO_ENGAGEMENT_ID))
    await db.flush()


async def demo_workspace_ready(db: AsyncSession) -> bool:
    investigation = await db.get(Investigation, DEMO_INVESTIGATION_ID)
    if investigation is None or investigation.status == "archived":
        return False
    required_ids = (
        (Target, DEMO_TARGET_ID),
        (Finding, DEMO_FINDING_ID),
        (InvestigationNote, DEMO_NOTE_ID),
        (InvestigationEvidence, DEMO_INVESTIGATION_EVIDENCE_ID),
        (EvidenceBookmark, DEMO_BOOKMARK_ID),
        (InvestigationTask, DEMO_TASK_ID),
        (PlaybookRun, DEMO_PLAYBOOK_RUN_ID),
        (Report, DEMO_REPORT_ID),
        (KnowledgeDocument, DEMO_KNOWLEDGE_DOCUMENT_ID),
        (IOC, DEMO_IOC_ID),
        (ThreatCampaign, DEMO_CAMPAIGN_ID),
        (Engagement, DEMO_ENGAGEMENT_ID),
        (CaseClosure, DEMO_CLOSURE_ID),
        (CaseDeliverable, DEMO_EXEC_DELIVERABLE_ID),
    )
    for model, item_id in required_ids:
        if await db.get(model, item_id) is None:
            return False
    return True


async def _ensure_demo_engagement(
    db: AsyncSession,
    user: User,
    now: datetime,
) -> None:
    engagement = await db.get(Engagement, DEMO_ENGAGEMENT_ID)
    if engagement is None:
        db.add(
            Engagement(
                id=DEMO_ENGAGEMENT_ID,
                title="[DEMO] Client Authorization Review",
                client_name="[DEMO] Example Client",
                client_contact="demo-approver@example.invalid",
                description=(
                    "Synthetic engagement metadata for demonstration only. "
                    "No real client, authorization record, or compromise is "
                    "represented."
                ),
                status="active",
                authorization_status="approved",
                start_date=now.date(),
                end_date=(now + timedelta(days=30)).date(),
                created_by=user.id,
            )
        )
    else:
        engagement.status = "active"
        engagement.authorization_status = "approved"
        db.add(engagement)
    if await db.get(EngagementScopeItem, DEMO_SCOPE_DOMAIN_ID) is None:
        db.add(
            EngagementScopeItem(
                id=DEMO_SCOPE_DOMAIN_ID,
                engagement_id=DEMO_ENGAGEMENT_ID,
                scope_type="domain",
                value="demo.raventech.invalid",
                description="Reserved synthetic demo domain.",
                status="in_scope",
                created_by=user.id,
            )
        )
    if await db.get(EngagementScopeItem, DEMO_SCOPE_IP_ID) is None:
        db.add(
            EngagementScopeItem(
                id=DEMO_SCOPE_IP_ID,
                engagement_id=DEMO_ENGAGEMENT_ID,
                scope_type="cidr",
                value="192.0.2.0/24",
                description="TEST-NET-1 documentation range for demo evidence.",
                status="in_scope",
                created_by=user.id,
            )
        )
    if await db.get(AuthorizationEvidence, DEMO_AUTH_EVIDENCE_ID) is None:
        db.add(
            AuthorizationEvidence(
                id=DEMO_AUTH_EVIDENCE_ID,
                engagement_id=DEMO_ENGAGEMENT_ID,
                title="[DEMO] Internal Defensive Assessment Approval",
                description=(
                    "Metadata only. Represents synthetic approval for demo "
                    "workspace review."
                ),
                evidence_type="internal_authorization",
                reference="demo://authorization/internal-review",
                status="approved",
                created_by=user.id,
            )
        )


async def _ensure_member(db: AsyncSession, user: User) -> None:
    result = await db.execute(
        select(InvestigationMember).where(
            InvestigationMember.investigation_id == DEMO_INVESTIGATION_ID,
            InvestigationMember.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        db.add(
            InvestigationMember(
                investigation_id=DEMO_INVESTIGATION_ID,
                user_id=user.id,
                role="owner",
                invited_by=user.id,
            )
        )


async def _ensure_target(db: AsyncSession, user: User) -> None:
    if await db.get(Target, DEMO_TARGET_ID) is None:
        db.add(
            Target(
                id=DEMO_TARGET_ID,
                investigation_id=DEMO_INVESTIGATION_ID,
                target_type="domain",
                target_value="demo.raventech.invalid",
                label="[DEMO] Reserved defensive target",
                notes="Synthetic target. No live recon should be performed.",
                created_by=user.id,
            )
        )


async def _ensure_recon_entities(db: AsyncSession) -> None:
    entities = (
        ReconEntity(
            id=DEMO_DOMAIN_ENTITY_ID,
            investigation_id=DEMO_INVESTIGATION_ID,
            entity_type="Domain",
            value="demo.raventech.invalid",
            display_name="[DEMO] Authorized domain",
            properties={"demo": True, "reserved": True},
            source="demo_passive_recon",
        ),
        ReconEntity(
            id=DEMO_IP_ENTITY_ID,
            investigation_id=DEMO_INVESTIGATION_ID,
            entity_type="IPAddress",
            value="192.0.2.10",
            display_name="[DEMO] TEST-NET address",
            properties={"demo": True, "reserved": True},
            source="demo_passive_recon",
        ),
        ReconEntity(
            id=DEMO_SERVICE_ENTITY_ID,
            investigation_id=DEMO_INVESTIGATION_ID,
            entity_type="Service",
            value="https://demo.raventech.invalid",
            display_name="[DEMO] HTTPS service",
            properties={"demo": True, "protocol": "https"},
            source="demo_passive_recon",
        ),
        ReconEntity(
            id=DEMO_TECH_ENTITY_ID,
            investigation_id=DEMO_INVESTIGATION_ID,
            entity_type="Technology",
            value="Reverse proxy",
            display_name="[DEMO] Reverse proxy",
            properties={"demo": True, "confidence": "medium"},
            source="demo_passive_recon",
        ),
    )
    for entity in entities:
        if await db.get(ReconEntity, entity.id) is None:
            db.add(entity)


async def _ensure_recon_relationships(db: AsyncSession) -> None:
    relationships = (
        ReconRelationship(
            id=DEMO_RELATIONSHIP_DOMAIN_IP_ID,
            investigation_id=DEMO_INVESTIGATION_ID,
            source_entity_id=DEMO_DOMAIN_ENTITY_ID,
            target_entity_id=DEMO_IP_ENTITY_ID,
            relationship_type="RESOLVES_TO",
            source="demo_passive_recon",
            properties={"demo": True, "statement": "Reserved domain maps to TEST-NET."},
        ),
        ReconRelationship(
            id=DEMO_RELATIONSHIP_DOMAIN_SERVICE_ID,
            investigation_id=DEMO_INVESTIGATION_ID,
            source_entity_id=DEMO_DOMAIN_ENTITY_ID,
            target_entity_id=DEMO_SERVICE_ENTITY_ID,
            relationship_type="HOSTS",
            source="demo_passive_recon",
            properties={"demo": True, "service": "https"},
        ),
        ReconRelationship(
            id=DEMO_RELATIONSHIP_SERVICE_TECH_ID,
            investigation_id=DEMO_INVESTIGATION_ID,
            source_entity_id=DEMO_SERVICE_ENTITY_ID,
            target_entity_id=DEMO_TECH_ENTITY_ID,
            relationship_type="RELATED_TO",
            source="demo_passive_recon",
            properties={"demo": True, "label": "service technology"},
        ),
    )
    for relationship in relationships:
        if await db.get(ReconRelationship, relationship.id) is None:
            db.add(relationship)


async def _ensure_finding(db: AsyncSession, user: User) -> None:
    if await db.get(Finding, DEMO_FINDING_ID) is None:
        db.add(
            Finding(
                id=DEMO_FINDING_ID,
                target_id=DEMO_TARGET_ID,
                investigation_id=DEMO_INVESTIGATION_ID,
                title="[DEMO] Public service configuration requires analyst review",
                description=(
                    "Stored passive evidence indicates a potential public exposure "
                    "for an authorized HTTPS service. The observed configuration "
                    "requires validation of business need, ownership, and defensive "
                    "controls. This is not a compromise claim."
                ),
                severity="medium",
                source="demo_passive_recon",
                raw_data={"demo": True, "live_request": False},
                normalized_data={
                    "affected_targets": ["demo.raventech.invalid"],
                    "frameworks": ["CIS Controls", "NIST CSF"],
                },
                confidence_score=82,
                risk_score=46,
                confidence="high",
                status="under_review",
                assigned_to=user.id,
                remediation_status="remediation_planned",
                remediation_owner=user.id,
                remediation_notes=(
                    "Defensive recommendation: confirm required exposure, document "
                    "approved controls, and preserve verification evidence."
                ),
                confidence_reasoning=(
                    "The finding is derived only from synthetic stored service "
                    "metadata and reserved identifiers."
                ),
                evidence_summary=(
                    "Reserved domain, TEST-NET IP, and HTTPS service metadata."
                ),
                review_history=[{"event": "demo_created", "demo": True}],
                created_by=user.id,
            )
        )
    if await db.get(FindingEvidence, DEMO_EVIDENCE_ID) is None:
        db.add(
            FindingEvidence(
                id=DEMO_EVIDENCE_ID,
                finding_id=DEMO_FINDING_ID,
                recon_entity_id=DEMO_SERVICE_ENTITY_ID,
                evidence_type="service_metadata",
                source="demo_passive_recon",
                description=(
                    "Synthetic HTTPS service metadata stored for demonstration."
                ),
                data={"demo": True, "reserved_target": True},
            )
        )


async def _ensure_note(db: AsyncSession, user: User) -> None:
    if await db.get(InvestigationNote, DEMO_NOTE_ID) is None:
        db.add(
            InvestigationNote(
                id=DEMO_NOTE_ID,
                investigation_id=DEMO_INVESTIGATION_ID,
                created_by=user.id,
                updated_by=user.id,
                title="[DEMO] Analyst scope and evidence note",
                content=(
                    "Synthetic case note for portfolio demonstrations.\n\n"
                    "- Scope uses reserved identifiers only.\n"
                    "- No live scanning or exploitation is represented.\n"
                    "- Defensive review focuses on ownership, logging, and "
                    "remediation evidence."
                ),
                note_type="analyst_note",
                pinned=True,
                references=[str(DEMO_FINDING_ID), str(DEMO_SERVICE_ENTITY_ID)],
            )
        )


async def _ensure_task(db: AsyncSession, user: User, now: datetime) -> None:
    if await db.get(InvestigationTask, DEMO_TASK_ID) is None:
        db.add(
            InvestigationTask(
                id=DEMO_TASK_ID,
                investigation_id=DEMO_INVESTIGATION_ID,
                title="[DEMO] Validate approved public service exposure",
                description=(
                    "Review stored evidence with the synthetic asset owner and "
                    "record the expected defensive controls."
                ),
                status="in_progress",
                priority="high",
                assigned_to=user.id,
                finding_id=DEMO_FINDING_ID,
                due_date=now + timedelta(days=7),
                created_by=user.id,
            )
        )


async def _ensure_evidence(db: AsyncSession, user: User) -> None:
    if await db.get(InvestigationEvidence, DEMO_INVESTIGATION_EVIDENCE_ID) is None:
        db.add(
            InvestigationEvidence(
                id=DEMO_INVESTIGATION_EVIDENCE_ID,
                investigation_id=DEMO_INVESTIGATION_ID,
                finding_id=DEMO_FINDING_ID,
                note_id=DEMO_NOTE_ID,
                task_id=DEMO_TASK_ID,
                title="[DEMO] Passive service evidence chain",
                description=(
                    "Synthetic evidence record linking the finding, analyst note, "
                    "and remediation task for demonstration."
                ),
                evidence_type="recon",
                source="demo_passive_recon",
                confidence=82,
                confidence_score=82,
                tags=["demo", "passive-recon", "evidence-chain"],
                analyst_comment=(
                    "Evidence is synthetic and reserved for release-candidate demos."
                ),
                review_status="reviewed",
                reviewed_by=user.id,
                reviewed_at=datetime.now(UTC),
                analyst_note="Review validates only the demo data model.",
                created_by=user.id,
            )
        )


async def _ensure_bookmark(db: AsyncSession, user: User) -> None:
    if await db.get(EvidenceBookmark, DEMO_BOOKMARK_ID) is None:
        db.add(
            EvidenceBookmark(
                id=DEMO_BOOKMARK_ID,
                investigation_id=DEMO_INVESTIGATION_ID,
                finding_id=DEMO_FINDING_ID,
                title="[DEMO] Key finding bookmark",
                note=(
                    "Bookmark used to show analyst-selected evidence during "
                    "portfolio and client demos."
                ),
                created_by=user.id,
            )
        )


async def _ensure_ioc(db: AsyncSession, now: datetime) -> None:
    if await db.get(IOC, DEMO_IOC_ID) is None:
        db.add(
            IOC(
                id=DEMO_IOC_ID,
                value="demo.raventech.invalid",
                normalized_value="demo.raventech.invalid",
                ioc_type="domain",
                source="demo_passive_recon",
                confidence="high",
                confidence_reason=(
                    "Synthetic IOC is linked to a reserved domain, finding, and "
                    "investigation for demonstration."
                ),
                first_seen=now,
                last_seen=now,
                tags=["demo", "reserved-domain", "defensive"],
                notes="Synthetic IOC. No attribution or compromise claim.",
            )
        )
    if await db.get(IOCObservation, DEMO_IOC_OBSERVATION_ID) is None:
        db.add(
            IOCObservation(
                id=DEMO_IOC_OBSERVATION_ID,
                ioc_id=DEMO_IOC_ID,
                investigation_id=DEMO_INVESTIGATION_ID,
                recon_entity_id=DEMO_DOMAIN_ENTITY_ID,
                source="demo_passive_recon",
                observation_count=1,
                evidence_quality=82,
                first_seen=now,
                last_seen=now,
                observation_metadata={
                    "demo": True,
                    "reserved": True,
                    "statement": "Observed only in synthetic demo data.",
                },
            )
        )


async def _ensure_threat_intelligence(
    db: AsyncSession,
    user: User,
    now: datetime,
) -> None:
    if await db.get(ThreatCampaign, DEMO_CAMPAIGN_ID) is None:
        db.add(
            ThreatCampaign(
                id=DEMO_CAMPAIGN_ID,
                name="[DEMO] Defensive Exposure Review Pattern",
                description=(
                    "Analyst-created synthetic campaign record used to demonstrate "
                    "internal IOC organization without attribution claims."
                ),
                status="monitoring",
                confidence="Medium",
                first_observed=now,
                last_observed=now,
                created_by=user.id,
                campaign_metadata={"demo": True, "synthetic": True},
            )
        )
    if await db.get(ThreatTechnique, DEMO_TECHNIQUE_ID) is None:
        db.add(
            ThreatTechnique(
                id=DEMO_TECHNIQUE_ID,
                technique_id="T1590",
                name="Gather Victim Network Information",
                tactic="Reconnaissance",
                procedure=(
                    "Mapped only as defensive context for reviewing authorized "
                    "external exposure. The demo performs no scanning."
                ),
                created_by=user.id,
            )
        )
    if await db.get(ThreatGroup, DEMO_GROUP_ID) is None:
        db.add(
            ThreatGroup(
                id=DEMO_GROUP_ID,
                name="[DEMO] Unattributed Defensive Pattern",
                aliases=["Synthetic demo pattern"],
                description=(
                    "Placeholder group for demonstrating analyst-approved "
                    "organization. No threat actor attribution is asserted."
                ),
                confidence="Low",
                notes="Synthetic grouping for portfolio demonstration only.",
                created_by=user.id,
            )
        )
    links = (
        (
            ThreatCampaignIndicator,
            DEMO_CAMPAIGN_IOC_LINK_ID,
            {
                "campaign_id": DEMO_CAMPAIGN_ID,
                "ioc_id": DEMO_IOC_ID,
            },
        ),
        (
            ThreatCampaignFinding,
            DEMO_CAMPAIGN_FINDING_LINK_ID,
            {
                "campaign_id": DEMO_CAMPAIGN_ID,
                "finding_id": DEMO_FINDING_ID,
            },
        ),
        (
            ThreatCampaignInvestigation,
            DEMO_CAMPAIGN_INVESTIGATION_LINK_ID,
            {
                "campaign_id": DEMO_CAMPAIGN_ID,
                "investigation_id": DEMO_INVESTIGATION_ID,
            },
        ),
        (
            ThreatCampaignTechnique,
            DEMO_CAMPAIGN_TECHNIQUE_LINK_ID,
            {
                "campaign_id": DEMO_CAMPAIGN_ID,
                "technique_id": DEMO_TECHNIQUE_ID,
            },
        ),
        (
            ThreatGroupCampaign,
            DEMO_GROUP_CAMPAIGN_LINK_ID,
            {
                "group_id": DEMO_GROUP_ID,
                "campaign_id": DEMO_CAMPAIGN_ID,
            },
        ),
    )
    for model, link_id, values in links:
        if await db.get(model, link_id) is None:
            db.add(model(id=link_id, **values))


async def _ensure_playbook_run(db: AsyncSession, user: User) -> None:
    if await db.get(PlaybookRun, DEMO_PLAYBOOK_RUN_ID) is None:
        db.add(
            PlaybookRun(
                id=DEMO_PLAYBOOK_RUN_ID,
                investigation_id=DEMO_INVESTIGATION_ID,
                finding_id=DEMO_FINDING_ID,
                playbook_id=PUBLIC_EXPOSURE_PLAYBOOK_ID,
                status="in_progress",
                started_by=user.id,
            )
        )
        await db.flush()
    statuses = ("completed", "in_progress", "pending", "pending")
    for index, (step_id, status) in enumerate(
        zip(PUBLIC_EXPOSURE_STEP_IDS, statuses, strict=True),
        start=1,
    ):
        run_step_id = uuid.UUID(
            f"70000000-0000-4000-8100-{index:012d}"
        )
        if await db.get(PlaybookRunStep, run_step_id) is None:
            db.add(
                PlaybookRunStep(
                    id=run_step_id,
                    playbook_run_id=DEMO_PLAYBOOK_RUN_ID,
                    playbook_step_id=step_id,
                    status=status,
                    analyst_note=(
                        "Synthetic evidence validated for demonstration."
                        if status == "completed"
                        else None
                    ),
                    completed_by=user.id if status == "completed" else None,
                    completed_at=datetime.now(UTC) if status == "completed" else None,
                )
            )


async def _ensure_report(db: AsyncSession, user: User, now: datetime) -> None:
    if await db.get(Report, DEMO_REPORT_ID) is not None:
        return
    markdown = """# [DEMO] Authorized External Exposure Review

> Synthetic defensive report. No real organization or compromise is represented.

## Executive Summary

One evidence-backed potential exposure review is in progress for a reserved
example service. The observed configuration requires analyst validation and a
documented defensive recommendation.

## Key Finding

- Medium: Public service configuration requires analyst review.

## Remediation

- Confirm business need and authorized scope.
- Validate defensive controls for the observed configuration.
- Record verification evidence before closure.
"""
    html = (
        "<h1>[DEMO] Authorized External Exposure Review</h1>"
        "<p><strong>Synthetic defensive report.</strong> No real organization "
        "or compromise is represented.</p>"
        "<h2>Executive Summary</h2>"
        "<p>One evidence-backed potential exposure review is in progress for a "
        "reserved example service. The observed configuration requires analyst "
        "validation and a documented defensive recommendation.</p>"
    )
    db.add(
        Report(
            id=DEMO_REPORT_ID,
            investigation_id=DEMO_INVESTIGATION_ID,
            generated_by=user.id,
            template_id=uuid.UUID("40000000-0000-4000-8000-000000000001"),
            title="[DEMO] Executive Defensive Assessment",
            report_type="executive",
            report_format="html",
            status="ready",
            file_size_bytes=len(markdown.encode()) + len(html.encode()),
            html_content=html,
            markdown_content=markdown,
            report_metadata={
                "demo": True,
                "synthetic": True,
                "disclaimer": "No real compromise claim.",
            },
            progress_label="Demo report ready",
            generated_at=now,
        )
    )


async def _ensure_closure(db: AsyncSession, user: User, now: datetime) -> None:
    if await db.get(CaseClosure, DEMO_CLOSURE_ID) is None:
        db.add(
            CaseClosure(
                id=DEMO_CLOSURE_ID,
                investigation_id=DEMO_INVESTIGATION_ID,
                status="approved",
                closure_summary=(
                    "[DEMO] Final handoff summary: scope, passive evidence, "
                    "remediation ownership, and client-ready reporting are prepared "
                    "for demonstration. No real compromise is represented."
                ),
                final_risk_rating="elevated",
                reviewed_by=user.id,
                approved_by=user.id,
                reviewed_at=now,
                approved_at=now,
            )
        )
    checklist = (
        (
            DEMO_CLOSURE_CHECK_SCOPE_ID,
            "scope_authorization_confirmed",
            "Scope and authorization confirmed",
            "Synthetic engagement authorization and reserved scope are approved.",
        ),
        (
            DEMO_CLOSURE_CHECK_REPORT_ID,
            "final_deliverables_prepared",
            "Final deliverables prepared",
            "Demo executive and technical deliverables are ready.",
        ),
    )
    for item_id, key, label, description in checklist:
        if await db.get(CaseClosureChecklistItem, item_id) is None:
            db.add(
                CaseClosureChecklistItem(
                    id=item_id,
                    investigation_id=DEMO_INVESTIGATION_ID,
                    closure_id=DEMO_CLOSURE_ID,
                    key=key,
                    label=label,
                    description=description,
                    status="completed",
                    required=True,
                    completed_by=user.id,
                    completed_at=now,
                )
            )
    deliverables = (
        (
            DEMO_EXEC_DELIVERABLE_ID,
            "[DEMO] Executive Defensive Assessment",
            "executive_report",
            "html",
            DEMO_REPORT_ID,
            "report://demo/executive-assessment",
        ),
        (
            DEMO_TECH_DELIVERABLE_ID,
            "[DEMO] Technical Evidence Summary",
            "technical_report",
            "md",
            DEMO_REPORT_ID,
            "report://demo/technical-evidence-summary",
        ),
        (
            DEMO_PACKAGE_DELIVERABLE_ID,
            "[DEMO] Final Client Deliverables Package Manifest",
            "final_package",
            None,
            None,
            "manifest://demo/final-client-deliverables",
        ),
    )
    for deliverable_id, title, deliverable_type, report_format, report_id, reference in deliverables:
        if await db.get(CaseDeliverable, deliverable_id) is None:
            db.add(
                CaseDeliverable(
                    id=deliverable_id,
                    investigation_id=DEMO_INVESTIGATION_ID,
                    title=title,
                    deliverable_type=deliverable_type,
                    status="ready",
                    report_id=report_id,
                    export_format=report_format,
                    file_reference=reference,
                    created_by=user.id,
                )
            )


async def _ensure_knowledge(db: AsyncSession) -> None:
    content = (
        "# Defensive Public Exposure Review\n\n"
        "Validate authorization, asset ownership, business need, access controls, "
        "logging, and remediation evidence before closing a public exposure review."
    )
    if await db.get(KnowledgeDocument, DEMO_KNOWLEDGE_DOCUMENT_ID) is None:
        db.add(
            KnowledgeDocument(
                id=DEMO_KNOWLEDGE_DOCUMENT_ID,
                source_type="playbooks",
                file_path="demo://defensive-public-exposure-review.md",
                title="[DEMO] Defensive Public Exposure Review",
                content=content,
                hash=hashlib.sha256(content.encode()).hexdigest(),
                tags=["demo", "defensive", "exposure-review"],
            )
        )
    if await db.get(KnowledgeChunk, DEMO_KNOWLEDGE_CHUNK_ID) is None:
        db.add(
            KnowledgeChunk(
                id=DEMO_KNOWLEDGE_CHUNK_ID,
                document_id=DEMO_KNOWLEDGE_DOCUMENT_ID,
                content=content,
                chunk_index=0,
                embedding_metadata={
                    "demo": True,
                    "framework": "CIS Controls",
                    "category": "exposure_review",
                },
            )
        )


async def _ensure_workflow_event(db: AsyncSession, user: User) -> None:
    if (
        await db.get(InvestigationWorkflowEvent, DEMO_WORKFLOW_EVENT_ID)
        is None
    ):
        db.add(
            InvestigationWorkflowEvent(
                id=DEMO_WORKFLOW_EVENT_ID,
                investigation_id=DEMO_INVESTIGATION_ID,
                actor_id=user.id,
                from_status="intake",
                to_status="active",
                reason="Synthetic demo case prepared for analyst review.",
            )
        )
