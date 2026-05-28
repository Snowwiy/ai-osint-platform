from __future__ import annotations

import json

from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.recon_entity import ReconEntity
from app.services.ai import analyst_service
from app.services.ai.knowledge_retriever import KnowledgeRetrievalResult
from app.services.ai.llm_provider import ProviderCompletion
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import VALID_AUTH_STATEMENT


class FakeProvider:
    def __init__(self, citation_id: str) -> None:
        self.citation_id = citation_id

    async def complete(self, _prompt: str) -> ProviderCompletion:
        payload = {
            "executive_summary": {
                "text": "The cited evidence is elevated risk.",
                "citation_ids": [self.citation_id],
            },
            "technical_summary": {
                "text": "The evidence supports defensive validation.",
                "citation_ids": [self.citation_id],
            },
            "observed_indicators": [
                {
                    "text": "example.com was observed.",
                    "citation_ids": [self.citation_id],
                }
            ],
            "suspicious_findings": [
                {
                    "text": "Threat reputation is elevated.",
                    "citation_ids": [self.citation_id],
                }
            ],
            "attack_hypotheses": [
                {
                    "text": "Validate whether the signal is active or historical.",
                    "citation_ids": [self.citation_id],
                }
            ],
            "severity": "high",
            "confidence": 80,
            "recommended_next_steps": [
                {
                    "action": "Validate and remediate the cited exposure.",
                    "rationale": "The cited evidence is high risk.",
                    "citation_ids": [self.citation_id],
                }
            ],
            "framework_mappings": [
                {
                    "framework": "NIST CSF",
                    "control": "DE.CM",
                    "rationale": "Evidence supports monitoring review.",
                    "citation_ids": [self.citation_id],
                }
            ],
        }
        return ProviderCompletion(
            status="completed",
            content=json.dumps(payload),
            model="claude-test",
        )


async def _no_knowledge(*_args, **_kwargs) -> KnowledgeRetrievalResult:
    return KnowledgeRetrievalResult(items=[])


async def test_analysis_non_member_gets_404(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    admin_user,
) -> None:
    investigation = Investigation(
        title="Private Analysis",
        owner_id=admin_user.id,
        authorization_statement=VALID_AUTH_STATEMENT,
        status="active",
    )
    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    response = await client.post(
        "/api/v1/analysis/investigation",
        headers=analyst_headers,
        json={"investigation_id": str(investigation.id)},
    )

    assert response.status_code == 404


async def test_investigation_analysis_endpoint_returns_grounded_response(
    monkeypatch,
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    finding = await _add_analysis_data(db, test_investigation.id)
    citation_id = f"finding:{finding.id}"
    monkeypatch.setattr(analyst_service, "retrieve_knowledge_context", _no_knowledge)
    monkeypatch.setattr(
        analyst_service,
        "get_llm_provider",
        lambda: FakeProvider(citation_id),
    )

    response = await client.post(
        "/api/v1/analysis/investigation",
        headers=analyst_headers,
        json={"investigation_id": str(test_investigation.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["model"] == "claude-test"
    assert body["executive_summary"]["citation_ids"] == [citation_id]
    assert body["citations"]


async def test_ioc_and_threat_context_analysis_endpoints(
    monkeypatch,
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    finding = await _add_analysis_data(db, test_investigation.id)
    citation_id = f"finding:{finding.id}"
    monkeypatch.setattr(analyst_service, "retrieve_knowledge_context", _no_knowledge)
    monkeypatch.setattr(
        analyst_service,
        "get_llm_provider",
        lambda: FakeProvider(citation_id),
    )

    ioc = await client.post(
        "/api/v1/analysis/ioc",
        headers=analyst_headers,
        json={
            "investigation_id": str(test_investigation.id),
            "ioc_type": "domain",
            "value": "example.com",
        },
    )
    context = await client.post(
        "/api/v1/analysis/threat-context",
        headers=analyst_headers,
        json={
            "investigation_id": str(test_investigation.id),
            "finding_ids": [str(finding.id)],
        },
    )

    assert ioc.status_code == 200
    assert ioc.json()["mode"] == "ioc"
    assert ioc.json()["target_value"] == "example.com"
    assert context.status_code == 200
    assert context.json()["mode"] == "threat_context"


async def test_admin_can_analyze_any_investigation(
    monkeypatch,
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    finding = await _add_analysis_data(db, test_investigation.id)
    citation_id = f"finding:{finding.id}"
    monkeypatch.setattr(analyst_service, "retrieve_knowledge_context", _no_knowledge)
    monkeypatch.setattr(
        analyst_service,
        "get_llm_provider",
        lambda: FakeProvider(citation_id),
    )

    response = await client.post(
        "/api/v1/analysis/investigation",
        headers=admin_headers,
        json={"investigation_id": str(test_investigation.id)},
    )

    assert response.status_code == 200


async def test_analysis_requires_auth(
    client: AsyncClient,
    test_investigation,
) -> None:
    response = await client.post(
        "/api/v1/analysis/investigation",
        json={"investigation_id": str(test_investigation.id)},
    )

    assert response.status_code == 401


async def _add_analysis_data(db: AsyncSession, investigation_id) -> Finding:
    entity = ReconEntity(
        investigation_id=investigation_id,
        entity_type="Domain",
        value="example.com",
        display_name="example.com",
        properties={"server": "Apache/2.4.49"},
        source="http",
    )
    db.add(entity)
    await db.flush()
    finding = Finding(
        investigation_id=investigation_id,
        title="Malicious VirusTotal reputation for example.com",
        description="VirusTotal reputation signals indicate malicious activity.",
        severity="high",
        confidence_score=90,
        risk_score=80,
        source="virustotal",
        raw_data={},
        normalized_data={},
        status="open",
        created_by=None,
    )
    db.add(finding)
    await db.commit()
    await db.refresh(finding)
    return finding
