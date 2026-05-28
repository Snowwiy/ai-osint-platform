from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.knowledge import KnowledgeSearchMode
from app.services.ai.evidence_builder import EvidenceBundle, EvidenceItem
from app.services.knowledge.retriever import retrieve_context

_DEFENSIVE_QUERIES: tuple[str, ...] = (
    "defensive exposure triage",
    "security misconfiguration mitigation",
    "incident response evidence handling",
    "secure configuration hardening",
)


@dataclass(frozen=True)
class KnowledgeRetrievalResult:
    items: list[EvidenceItem]
    mode: KnowledgeSearchMode = "keyword"


async def retrieve_knowledge_context(
    db: AsyncSession,
    evidence: EvidenceBundle,
    *,
    mode: KnowledgeSearchMode = "keyword",
    limit: int = 8,
) -> KnowledgeRetrievalResult:
    _ = db, mode
    results: list[EvidenceItem] = []
    for query in _queries(evidence):
        if len(results) >= limit:
            break
        context = retrieve_context(query, top_k=max(1, min(3, limit - len(results))))
        for chunk, citation in zip(
            context.matched_chunks,
            context.citations,
            strict=False,
        ):
            results.append(
                EvidenceItem(
                    id=citation.id,
                    source_type="knowledge_document",
                    title=chunk.title,
                    summary=chunk.content,
                    metadata={
                        "citation_id": citation.id,
                        "document_id": citation.document_id,
                        "chunk_id": citation.chunk_id,
                        "source": citation.source,
                        "framework": citation.framework,
                        "category": citation.category,
                        "confidence_score": int(citation.confidence * 100),
                        "tags": chunk.tags,
                    },
                )
            )
    return KnowledgeRetrievalResult(items=_dedupe(results)[:limit], mode="keyword")


def _queries(evidence: EvidenceBundle) -> list[str]:
    queries: list[str] = []
    queries.extend(evidence.focus_terms[:10])
    for item in evidence.items[:10]:
        queries.append(item.title)
    queries.extend(_DEFENSIVE_QUERIES)
    return _dedupe_strings(queries)


def _dedupe(items: list[EvidenceItem]) -> list[EvidenceItem]:
    deduped: dict[str, EvidenceItem] = {}
    for item in items:
        deduped.setdefault(item.id, item)
    return list(deduped.values())


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        clean = value.strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            deduped.append(clean)
    return deduped
