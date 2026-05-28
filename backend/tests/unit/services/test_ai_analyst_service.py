from __future__ import annotations

import json

from app.models.finding import Finding
from app.models.recon_entity import ReconEntity
from app.schemas.analysis import InvestigationAnalysisRequest
from app.services.ai import analyst_service
from app.services.ai.evidence_builder import EvidenceItem
from app.services.ai.knowledge_retriever import KnowledgeRetrievalResult
from app.services.ai.llm_provider import ProviderCompletion
from sqlalchemy.ext.asyncio import AsyncSession


class FakeProvider:
    def __init__(self, completion: ProviderCompletion) -> None:
        self.completion = completion

    async def complete(self, prompt: str) -> ProviderCompletion:
        assert "Evidence:" in prompt
        return self.completion


async def _no_knowledge(*_args, **_kwargs) -> KnowledgeRetrievalResult:
    return KnowledgeRetrievalResult(items=[])


async def _knowledge(*_args, **_kwargs) -> KnowledgeRetrievalResult:
    return KnowledgeRetrievalResult(
        items=[
            EvidenceItem(
                id="knowledge_document:doc-1",
                source_type="knowledge_document",
                title="OWASP Security Misconfiguration",
                summary="Harden exposed service headers.",
                metadata={
                    "document_id": "doc-1",
                    "source_type": "frameworks",
                    "file_path": "/kb/owasp.md",
                },
            )
        ]
    )


async def test_analysis_returns_provider_unavailable_with_citations(
    monkeypatch,
    db: AsyncSession,
    analyst_user,
    test_investigation,
) -> None:
    monkeypatch.setattr(analyst_service, "retrieve_knowledge_context", _no_knowledge)
    await _add_analysis_evidence(db, test_investigation.id)

    response = await analyst_service.analyze_investigation(
        db,
        analyst_user,
        InvestigationAnalysisRequest(investigation_id=test_investigation.id),
        provider=FakeProvider(
            ProviderCompletion(
                status="provider_unavailable",
                error="ANTHROPIC_API_KEY is not configured.",
            )
        ),
    )

    assert response.status == "provider_unavailable"
    assert response.citations
    assert response.executive_summary.citation_ids
    assert response.errors == ["ANTHROPIC_API_KEY is not configured."]


async def test_analysis_handles_timeout_and_malformed_provider_response(
    monkeypatch,
    db: AsyncSession,
    analyst_user,
    test_investigation,
) -> None:
    monkeypatch.setattr(analyst_service, "retrieve_knowledge_context", _no_knowledge)
    await _add_analysis_evidence(db, test_investigation.id)

    timeout = await analyst_service.analyze_investigation(
        db,
        analyst_user,
        InvestigationAnalysisRequest(investigation_id=test_investigation.id),
        provider=FakeProvider(
            ProviderCompletion(
                status="provider_timeout",
                error="Anthropic provider request timed out.",
            )
        ),
    )
    malformed = await analyst_service.analyze_investigation(
        db,
        analyst_user,
        InvestigationAnalysisRequest(investigation_id=test_investigation.id),
        provider=FakeProvider(
            ProviderCompletion(status="completed", content="not-json")
        ),
    )

    assert timeout.status == "provider_timeout"
    assert malformed.status == "malformed_response"
    assert malformed.citations


async def test_analysis_accepts_only_grounded_llm_citations(
    monkeypatch,
    db: AsyncSession,
    analyst_user,
    test_investigation,
) -> None:
    monkeypatch.setattr(analyst_service, "retrieve_knowledge_context", _knowledge)
    finding = await _add_analysis_evidence(db, test_investigation.id)
    citation_id = f"finding:{finding.id}"
    payload = {
        "executive_summary": {
            "text": "The cited finding is high risk.",
            "citation_ids": [citation_id],
        },
        "technical_summary": {
            "text": "The evidence links reputation and exposed service data.",
            "citation_ids": [citation_id],
        },
        "observed_indicators": [
            {"text": "example.com is observed.", "citation_ids": [citation_id]}
        ],
        "suspicious_findings": [
            {"text": "Reputation score is elevated.", "citation_ids": [citation_id]}
        ],
        "attack_hypotheses": [
            {
                "text": "Validate whether the signal is active or historical.",
                "citation_ids": [citation_id],
            }
        ],
        "severity": "high",
        "confidence": 82,
        "recommended_next_steps": [
            {
                "action": "Validate ownership and remediate exposure.",
                "rationale": "The cited evidence is high risk.",
                "citation_ids": [citation_id],
            }
        ],
        "framework_mappings": [
            {
                "framework": "NIST CSF",
                "control": "DE.CM",
                "rationale": "Monitoring evidence supports detection review.",
                "citation_ids": [citation_id],
            }
        ],
    }

    response = await analyst_service.analyze_investigation(
        db,
        analyst_user,
        InvestigationAnalysisRequest(investigation_id=test_investigation.id),
        provider=FakeProvider(
            ProviderCompletion(
                status="completed",
                content=json.dumps(payload),
                model="claude-test",
            )
        ),
    )

    allowed_ids = {citation.id for citation in response.citations}
    assert response.status == "completed"
    assert response.model == "claude-test"
    assert response.executive_summary.citation_ids == [citation_id]
    assert all(
        citation in allowed_ids
        for item in response.suspicious_findings
        for citation in item.citation_ids
    )


async def _add_analysis_evidence(db: AsyncSession, investigation_id) -> Finding:
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
