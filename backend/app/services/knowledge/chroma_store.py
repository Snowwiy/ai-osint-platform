from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_COLLECTION_NAME = "knowledge_collection"


@dataclass(frozen=True)
class VectorFilters:
    source_type: str | None = None
    tags: list[str] | None = None


@dataclass(frozen=True)
class VectorChunk:
    chunk_id: str
    document_id: uuid.UUID
    content: str
    metadata: dict[str, Any]
    embedding: list[float]


class ChromaKnowledgeStore:
    def __init__(self, persist_directory: str) -> None:
        self._persist_directory = str(Path(persist_directory))
        self._collection = None

    def upsert_chunks(self, chunks: list[VectorChunk]) -> None:
        if not chunks:
            return
        collection = self._get_collection()
        collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.content for chunk in chunks],
            embeddings=[chunk.embedding for chunk in chunks],
            metadatas=[_chroma_metadata(chunk.metadata) for chunk in chunks],
        )

    def delete_document(self, document_id: uuid.UUID) -> None:
        collection = self._get_collection()
        collection.delete(where={"document_id": str(document_id)})

    def search(
        self,
        query_embedding: list[float],
        *,
        query: str,
        limit: int,
        filters: VectorFilters,
    ) -> list[dict[str, Any]]:
        collection = self._get_collection()
        where = _where(filters)
        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": limit,
        }
        if where:
            kwargs["where"] = where
        result = collection.query(**kwargs)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        matches: list[dict[str, Any]] = []
        for index, document in enumerate(documents):
            distance = distances[index] if index < len(distances) else None
            score = 1.0 - float(distance) if isinstance(distance, int | float) else 0.0
            matches.append(
                {
                    "document_id": metadatas[index].get("document_id"),
                    "content": document,
                    "score": score,
                    "metadata": metadatas[index],
                }
            )
        return matches

    def _get_collection(self) -> Any:
        if self._collection is None:
            import chromadb  # type: ignore[import-not-found]

            client = chromadb.PersistentClient(path=self._persist_directory)
            self._collection = client.get_or_create_collection(_COLLECTION_NAME)
        return self._collection


def _where(filters: VectorFilters) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = []
    if filters.source_type:
        clauses.append({"source_type": filters.source_type})
    for tag in filters.tags or []:
        clauses.append({"tags": {"$contains": tag}})
    if not clauses:
        return {}
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _chroma_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    clean: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if isinstance(value, str | int | float | bool):
            clean[key] = value
        elif isinstance(value, list):
            clean[key] = ",".join(str(item) for item in value)
    return clean
