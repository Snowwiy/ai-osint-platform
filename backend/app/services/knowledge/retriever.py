from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from app.schemas.knowledge import KnowledgeFramework

_DEFAULT_TOP_K = 5
_SUPPORTED_SUFFIXES = {".md", ".txt"}
_FRAMEWORKS: tuple[KnowledgeFramework, ...] = (
    "MITRE ATT&CK",
    "NIST CSF",
    "NIST 800-53",
    "CIS Controls",
    "OWASP Top 10",
    "Sigma",
    "YARA",
    "DFIR",
    "Threat Intelligence",
    "Secure Architecture",
    "Cloud Security",
)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True)
class KnowledgeDocument:
    id: str
    title: str
    source: str
    framework: KnowledgeFramework
    category: str
    content: str
    tags: list[str]
    confidence: float
    created_at: datetime


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    document_id: str
    title: str
    source: str
    framework: KnowledgeFramework
    category: str
    content: str
    tags: list[str]
    confidence: float
    created_at: datetime
    score: float = 0.0


@dataclass(frozen=True)
class KnowledgeCitation:
    id: str
    document_id: str
    chunk_id: str
    title: str
    source: str
    framework: KnowledgeFramework
    category: str
    confidence: float


@dataclass(frozen=True)
class KnowledgeRetrievalResult:
    query: str
    matched_chunks: list[KnowledgeChunk] = field(default_factory=list)
    citations: list[KnowledgeCitation] = field(default_factory=list)
    frameworks: list[KnowledgeFramework] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def citation_ids(self) -> list[str]:
        return [citation.id for citation in self.citations]


class LocalKnowledgeRetriever:
    def __init__(self, dataset_path: Path | None = None) -> None:
        self._dataset_path = dataset_path or default_dataset_path()

    def retrieve_context(
        self,
        query: str,
        frameworks: Sequence[str] | None = None,
        top_k: int = _DEFAULT_TOP_K,
    ) -> KnowledgeRetrievalResult:
        clean_query = query.strip()
        if not clean_query or top_k < 1:
            return KnowledgeRetrievalResult(query=clean_query)

        framework_filter = _normalize_framework_filter(frameworks)
        documents = [
            document
            for document in self._load_documents()
            if framework_filter is None or document.framework in framework_filter
        ]
        chunks = [
            chunk
            for document in documents
            for chunk in _chunk_document(document)
        ]
        query_tokens = _tokens(clean_query)
        scored = [
            _score_chunk(chunk, clean_query, query_tokens)
            for chunk in chunks
        ]
        matches = [
            chunk
            for chunk in sorted(
                scored,
                key=lambda item: (
                    item.score,
                    item.confidence,
                    item.framework,
                    item.title,
                    item.id,
                ),
                reverse=True,
            )
            if chunk.score > 0
        ][:top_k]
        citations = [_citation_from_chunk(chunk) for chunk in matches]
        frameworks_found = _dedupe_frameworks([chunk.framework for chunk in matches])
        confidence = _result_confidence(matches)
        return KnowledgeRetrievalResult(
            query=clean_query,
            matched_chunks=matches,
            citations=citations,
            frameworks=frameworks_found,
            confidence=confidence,
        )

    def _load_documents(self) -> list[KnowledgeDocument]:
        if not self._dataset_path.exists():
            return []
        files = [
            path
            for path in self._dataset_path.rglob("*")
            if path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES
        ]
        documents: list[KnowledgeDocument] = []
        for path in sorted(files):
            document = _document_from_file(path)
            if document is not None:
                documents.append(document)
        return documents


def retrieve_context(
    query: str,
    frameworks: Sequence[str] | None = None,
    top_k: int = _DEFAULT_TOP_K,
) -> KnowledgeRetrievalResult:
    return LocalKnowledgeRetriever().retrieve_context(
        query,
        frameworks=frameworks,
        top_k=top_k,
    )


def default_dataset_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "knowledge"


def _document_from_file(path: Path) -> KnowledgeDocument | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    metadata, content = _split_frontmatter(raw)
    framework = _framework(metadata.get("framework"))
    if framework is None:
        return None
    clean_content = content.strip()
    if not clean_content:
        return None
    title = metadata.get("title") or _title_from_content(clean_content) or path.stem
    created_at = _created_at(metadata.get("created_at"), path)
    return KnowledgeDocument(
        id=_stable_id(path),
        title=title,
        source=metadata.get("source") or "curated-local",
        framework=framework,
        category=metadata.get("category") or "General Defensive Guidance",
        content=clean_content,
        tags=_tags(metadata.get("tags")),
        confidence=_confidence(metadata.get("confidence")),
        created_at=created_at,
    )


def _split_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    normalized = raw.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized
    _, frontmatter, content = normalized.split("---", maxsplit=2)
    metadata: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", maxsplit=1)
        metadata[key.strip().lower()] = value.strip()
    return metadata, content


def _chunk_document(document: KnowledgeDocument) -> list[KnowledgeChunk]:
    sections = _sections(document.content)
    return [
        KnowledgeChunk(
            id=f"{document.id}:chunk:{index}",
            document_id=document.id,
            title=document.title,
            source=document.source,
            framework=document.framework,
            category=document.category,
            content=f"{document.title}\n\n{section}",
            tags=document.tags,
            confidence=document.confidence,
            created_at=document.created_at,
        )
        for index, section in enumerate(sections)
    ]


def _sections(content: str) -> list[str]:
    sections: list[str] = []
    current: list[str] = []
    for line in content.splitlines():
        if line.startswith("#") and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())
    return [section for section in sections if section]


def _score_chunk(
    chunk: KnowledgeChunk,
    query: str,
    query_tokens: list[str],
) -> KnowledgeChunk:
    haystack = " ".join(
        [
            chunk.title,
            chunk.framework,
            chunk.category,
            " ".join(chunk.tags),
            chunk.content,
        ]
    ).lower()
    if not query_tokens:
        return chunk

    score = 0.0
    for token in query_tokens:
        score += haystack.count(token)
        if token in chunk.title.lower():
            score += 3.0
        if token in chunk.category.lower():
            score += 2.0
        if token in {tag.lower() for tag in chunk.tags}:
            score += 2.0
        if token in chunk.framework.lower():
            score += 1.0

    phrase = query.lower()
    if phrase in haystack:
        score += 4.0

    length_penalty = max(1.0, math.log(len(_tokens(chunk.content)) + 3))
    normalized_score = score / length_penalty
    confidence = _chunk_confidence(chunk.confidence, normalized_score)
    return KnowledgeChunk(
        id=chunk.id,
        document_id=chunk.document_id,
        title=chunk.title,
        source=chunk.source,
        framework=chunk.framework,
        category=chunk.category,
        content=chunk.content,
        tags=chunk.tags,
        confidence=confidence,
        created_at=chunk.created_at,
        score=round(normalized_score, 4),
    )


def _citation_from_chunk(chunk: KnowledgeChunk) -> KnowledgeCitation:
    return KnowledgeCitation(
        id=f"knowledge:{chunk.id}",
        document_id=chunk.document_id,
        chunk_id=chunk.id,
        title=chunk.title,
        source=chunk.source,
        framework=chunk.framework,
        category=chunk.category,
        confidence=chunk.confidence,
    )


def _normalize_framework_filter(
    frameworks: Sequence[str] | None,
) -> set[KnowledgeFramework] | None:
    if not frameworks:
        return None
    allowed = {framework.lower(): framework for framework in _FRAMEWORKS}
    normalized = {
        allowed[item.strip().lower()]
        for item in frameworks
        if item.strip().lower() in allowed
    }
    return normalized


def _framework(value: str | None) -> KnowledgeFramework | None:
    if value is None:
        return None
    for framework in _FRAMEWORKS:
        if value.strip().lower() == framework.lower():
            return framework
    return None


def _tags(value: str | None) -> list[str]:
    if not value:
        return []
    return [
        tag.strip().lower()
        for tag in value.split(",")
        if tag.strip()
    ]


def _confidence(value: str | None) -> float:
    if value is None:
        return 0.75
    try:
        parsed = float(value)
    except ValueError:
        return 0.75
    return max(0.0, min(1.0, parsed))


def _created_at(value: str | None, path: Path) -> datetime:
    if value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return datetime.fromtimestamp(path.stat().st_mtime, UTC)


def _title_from_content(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None


def _stable_id(path: Path) -> str:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]
    return f"local-{path.stem.lower().replace('_', '-')}-{digest}"


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9-]{1,}", value.lower())
        if token not in _STOPWORDS
    ]


def _chunk_confidence(base_confidence: float, score: float) -> float:
    if score <= 0:
        return base_confidence
    confidence = min(1.0, base_confidence + min(0.2, score / 25))
    return round(confidence, 3)


def _result_confidence(matches: list[KnowledgeChunk]) -> float:
    if not matches:
        return 0.0
    return round(sum(chunk.confidence for chunk in matches) / len(matches), 3)


def _dedupe_frameworks(
    frameworks: list[KnowledgeFramework],
) -> list[KnowledgeFramework]:
    seen: set[KnowledgeFramework] = set()
    deduped: list[KnowledgeFramework] = []
    for framework in frameworks:
        if framework not in seen:
            seen.add(framework)
            deduped.append(cast(KnowledgeFramework, framework))
    return deduped
