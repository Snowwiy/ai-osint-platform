from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.knowledge import KnowledgeSearchMode, KnowledgeSourceType
from app.services.ai.evidence_builder import EvidenceBundle, EvidenceItem
from app.services.knowledge.knowledge_service import (
    KnowledgeSearchFilters,
    search_knowledge,
)

_FRAMEWORK_QUERIES: tuple[str, ...] = (
    "MITRE ATT&CK defensive technique mapping",
    "OWASP security misconfiguration mitigation",
    "NIST CSF detect respond recover controls",
    "NIST 800-53 security control mitigation",
    "ISO 27001 risk treatment control",
    "CIS Controls secure configuration monitoring",
)


@dataclass(frozen=True)
class KnowledgeRetrievalResult:
    items: list[EvidenceItem]
    mode: KnowledgeSearchMode = "hybrid"


async def retrieve_knowledge_context(
    db: AsyncSession,
    evidence: EvidenceBundle,
    *,
    mode: KnowledgeSearchMode = "hybrid",
    limit: int = 8,
) -> KnowledgeRetrievalResult:
    queries = _queries(evidence)
    results: list[EvidenceItem] = []
    for query in queries:
        if len(results) >= limit:
            break
        results.extend(
            await _search_with_fallback(
                db,
                query=query,
                mode=mode,
                limit=max(1, min(3, limit - len(results))),
            )
        )
    return KnowledgeRetrievalResult(items=_dedupe(results)[:limit], mode=mode)


async def _search_with_fallback(
    db: AsyncSession,
    *,
    query: str,
    mode: KnowledgeSearchMode,
    limit: int,
) -> list[EvidenceItem]:
    source_priority: tuple[KnowledgeSourceType | None, ...] = (
        "frameworks",
        "playbooks",
        "security_notes",
        "osint_notes",
        None,
    )
    items: list[EvidenceItem] = []
    for source_type in source_priority:
        try:
            response = await search_knowledge(
                db,
                query=query,
                mode=mode,
                filters=KnowledgeSearchFilters(source_type=source_type, tags=None),
                limit=limit,
            )
        except Exception:
            if mode == "keyword":
                continue
            try:
                response = await search_knowledge(
                    db,
                    query=query,
                    mode="keyword",
                    filters=KnowledgeSearchFilters(source_type=source_type, tags=None),
                    limit=limit,
                )
            except Exception:
                continue
        for match in response.items:
            items.append(
                EvidenceItem(
                    id=f"knowledge_document:{match.document_id}",
                    source_type="knowledge_document",
                    title=match.title,
                    summary=match.chunk,
                    metadata={
                        "document_id": str(match.document_id),
                        "source_type": match.source_type,
                        "file_path": match.file_path,
                        "score": match.score,
                        "tags": match.tags,
                    },
                )
            )
        if items:
            break
    return items


def _queries(evidence: EvidenceBundle) -> list[str]:
    queries: list[str] = []
    queries.extend(_FRAMEWORK_QUERIES)
    queries.extend(evidence.focus_terms[:10])
    for item in evidence.items[:10]:
        queries.append(item.title)
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
