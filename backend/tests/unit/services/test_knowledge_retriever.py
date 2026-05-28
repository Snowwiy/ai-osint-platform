from __future__ import annotations

from app.services.knowledge.retriever import LocalKnowledgeRetriever, retrieve_context


def test_retrieve_context_returns_defensive_rdp_guidance() -> None:
    result = retrieve_context("exposed RDP", top_k=3)

    assert result.matched_chunks
    assert result.matched_chunks[0].framework == "CIS Controls"
    assert "RDP" in result.matched_chunks[0].content
    assert result.citation_ids == [citation.id for citation in result.citations]
    assert result.confidence > 0


def test_retrieve_context_filters_by_framework() -> None:
    result = retrieve_context(
        "incident response evidence",
        frameworks=["NIST CSF"],
        top_k=5,
    )

    assert result.matched_chunks
    assert set(result.frameworks) == {"NIST CSF"}
    assert all(chunk.framework == "NIST CSF" for chunk in result.matched_chunks)


def test_retrieve_context_empty_dataset_returns_safe_fallback(tmp_path) -> None:
    result = LocalKnowledgeRetriever(tmp_path).retrieve_context("exposed RDP")

    assert result.query == "exposed RDP"
    assert result.matched_chunks == []
    assert result.citation_ids == []
    assert result.frameworks == []
    assert result.confidence == 0


def test_retrieve_context_citations_match_chunks() -> None:
    result = retrieve_context("server header disclosure", top_k=2)

    chunk_ids = {chunk.id for chunk in result.matched_chunks}
    assert chunk_ids
    assert {citation.chunk_id for citation in result.citations} == chunk_ids
    assert all(citation.id.startswith("knowledge:") for citation in result.citations)
