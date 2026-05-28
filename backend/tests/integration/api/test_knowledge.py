from __future__ import annotations

from app.models.knowledge_document import KnowledgeDocument
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class FakeEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]


class FakeVectorStore:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, object]] = {}

    def upsert_chunks(self, chunks) -> None:
        for chunk in chunks:
            self.items[chunk.chunk_id] = {
                "document_id": str(chunk.document_id),
                "content": chunk.content,
                "metadata": chunk.metadata,
                "embedding": chunk.embedding,
            }

    def delete_document(self, document_id) -> None:
        doc_id = str(document_id)
        self.items = {
            key: value
            for key, value in self.items.items()
            if value["document_id"] != doc_id
        }

    def search(self, query_embedding, *, query: str, limit: int, filters):
        matches = []
        for value in self.items.values():
            metadata = value["metadata"]
            if (
                filters.source_type
                and metadata.get("source_type") != filters.source_type
            ):
                continue
            if filters.tags and not set(filters.tags).issubset(
                set(metadata.get("tags", []))
            ):
                continue
            if query.lower() not in str(value["content"]).lower():
                continue
            matches.append(
                {
                    "document_id": value["document_id"],
                    "content": value["content"],
                    "score": 0.95,
                    "metadata": metadata,
                }
            )
        return matches[:limit]


async def test_knowledge_index_requires_admin(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    tmp_path,
) -> None:
    response = await client.post(
        "/api/v1/knowledge/index",
        headers=analyst_headers,
        json={"paths": [str(tmp_path)], "source_type": "security_notes"},
    )

    assert response.status_code == 403


async def test_admin_indexes_markdown_and_deduplicates_by_hash(
    monkeypatch,
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    tmp_path,
) -> None:
    from app.services.knowledge import knowledge_service

    note = tmp_path / "dns.md"
    note.write_text("# DNS Playbook\n\nUse passive DNS. #dns\n", encoding="utf-8")
    fake_store = FakeVectorStore()
    monkeypatch.setattr(knowledge_service, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(knowledge_service, "get_vector_store", lambda: fake_store)

    payload = {"paths": [str(tmp_path)], "source_type": "playbooks"}
    first = await client.post(
        "/api/v1/knowledge/index",
        headers=admin_headers,
        json=payload,
    )
    second = await client.post(
        "/api/v1/knowledge/index",
        headers=admin_headers,
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["documents_indexed"] == 1
    assert second.json()["documents_skipped"] == 1
    documents = (await db.execute(select(KnowledgeDocument))).scalars().all()
    assert len(documents) == 1
    assert documents[0].title == "DNS Playbook"
    assert fake_store.items


async def test_knowledge_documents_filter_by_tag_and_source_type(
    monkeypatch,
    client: AsyncClient,
    admin_headers: dict[str, str],
    tmp_path,
) -> None:
    from app.services.knowledge import knowledge_service

    (tmp_path / "osint.md").write_text("# OSINT\n\n#osint\n", encoding="utf-8")
    monkeypatch.setattr(knowledge_service, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(knowledge_service, "get_vector_store", FakeVectorStore)
    await client.post(
        "/api/v1/knowledge/index",
        headers=admin_headers,
        json={"paths": [str(tmp_path)], "source_type": "osint_notes"},
    )

    response = await client.get(
        "/api/v1/knowledge/documents",
        headers=admin_headers,
        params={"tags": "osint", "source_type": "osint_notes"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["source_type"] == "osint_notes"


async def test_knowledge_search_keyword_semantic_and_hybrid(
    monkeypatch,
    client: AsyncClient,
    admin_headers: dict[str, str],
    tmp_path,
) -> None:
    from app.services.knowledge import knowledge_service

    note = tmp_path / "ir.md"
    note.write_text(
        "# Incident Response\n\nContain malware quickly. #ir\n", encoding="utf-8"
    )
    fake_store = FakeVectorStore()
    monkeypatch.setattr(knowledge_service, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(knowledge_service, "get_vector_store", lambda: fake_store)
    await client.post(
        "/api/v1/knowledge/index",
        headers=admin_headers,
        json={"paths": [str(tmp_path)], "source_type": "frameworks"},
    )

    for mode in ("keyword", "semantic", "hybrid"):
        response = await client.get(
            "/api/v1/knowledge/search",
            headers=admin_headers,
            params={"q": "malware", "mode": mode, "source_type": "frameworks"},
        )
        assert response.status_code == 200
        assert response.json()["items"]
        assert response.json()["items"][0]["title"] == "Incident Response"
