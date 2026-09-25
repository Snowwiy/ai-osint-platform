from __future__ import annotations

from pathlib import Path

from app.models.knowledge_document import KnowledgeDocument
from app.models.knowledge_link import KnowledgeLink
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


async def test_legacy_admin_path_indexing_is_disabled(
    monkeypatch,
    client: AsyncClient,
    admin_headers: dict[str, str],
    tmp_path,
) -> None:
    (tmp_path / "dns.md").write_text("# DNS Playbook\n", encoding="utf-8")
    response = await client.post(
        "/api/v1/knowledge/index",
        headers=admin_headers,
        json={"paths": [str(tmp_path)], "source_type": "playbooks"},
    )
    assert response.status_code == 410


async def test_knowledge_documents_filter_by_tag_and_source_type(
    monkeypatch,
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    tmp_path,
) -> None:
    from app.api.v1 import knowledge as knowledge_api
    from app.core.config import settings
    from app.models.knowledge_source import KnowledgeSource
    from app.services.knowledge import knowledge_service, source_service

    def import_root():
        root = tmp_path / "imports"
        root.mkdir(exist_ok=True)
        return root

    async def no_queue(*_args, **_kwargs):
        return None

    monkeypatch.setattr(source_service, "import_root", import_root)
    monkeypatch.setattr(
        knowledge_api, "settings_native_jobs_unavailable", lambda: False
    )
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", "desktop")
    monkeypatch.setattr(knowledge_api, "_queue_source_sync", no_queue)
    monkeypatch.setattr(knowledge_service, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(knowledge_service, "get_vector_store", FakeVectorStore)
    response = await client.post(
        "/api/v1/knowledge/sources/obsidian-vault",
        headers={**admin_headers, "Origin": "tauri://localhost"},
        data={
            "name": "Test vault",
            "trust_level": "internal",
            "verification_status": "unverified",
        },
        files=[("files", ("nested/osint.md", b"# OSINT\n\n#osint\n", "text/markdown"))],
    )
    assert response.status_code == 202
    source = await db.get(KnowledgeSource, response.json()["id"])
    assert source is not None and str(tmp_path) not in response.text
    assert source.verification_status == "unverified"
    sync_result = await source_service.sync_knowledge_source(db, source.id)
    assert sync_result["indexed"] == 1, (
        sync_result,
        source.status,
        source.error_summary,
    )
    stored_documents = (await db.execute(select(KnowledgeDocument))).scalars().all()
    assert [(item.source_type, item.tags) for item in stored_documents] == [
        ("osint_notes", ["osint"])
    ]
    await db.commit()

    documents_response = await client.get(
        "/api/v1/knowledge/documents",
        headers=admin_headers,
        params={"tags": "osint", "source_type": "osint_notes"},
    )

    assert documents_response.status_code == 200
    source_filter_response = await client.get(
        "/api/v1/knowledge/documents",
        headers=admin_headers,
        params={"source_type": "osint_notes"},
    )
    tag_filter_response = await client.get(
        "/api/v1/knowledge/documents", headers=admin_headers, params={"tags": "osint"}
    )
    assert source_filter_response.json()["total"] == 1, source_filter_response.json()
    assert tag_filter_response.json()["total"] == 1, tag_filter_response.json()
    assert documents_response.json()["total"] == 1
    assert documents_response.json()["items"][0]["source_type"] == "osint_notes"
    assert documents_response.json()["items"][0]["relative_name"] == "nested/osint.md"


async def test_browser_origin_cannot_attach_local_knowledge_files(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/v1/knowledge/sources/obsidian-vault",
        headers={**admin_headers, "Origin": "http://localhost:5173"},
        data={"name": "Should not attach"},
        files=[("files", ("note.md", b"# selected", "text/markdown"))],
    )
    assert response.status_code == 403


async def test_incremental_sync_preserves_identity_reconciles_links_and_originals(
    monkeypatch,
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    tmp_path,
) -> None:
    from app.api.v1 import knowledge as knowledge_api
    from app.core.config import settings
    from app.models.knowledge_source import KnowledgeSource
    from app.services.knowledge import knowledge_service, source_service

    def import_root():
        root = tmp_path / "imports"
        root.mkdir(exist_ok=True)
        return root

    async def no_queue(*_args, **_kwargs):
        return None

    monkeypatch.setattr(source_service, "import_root", import_root)
    monkeypatch.setattr(
        knowledge_api, "settings_native_jobs_unavailable", lambda: False
    )
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", "desktop")
    monkeypatch.setattr(knowledge_api, "_queue_source_sync", no_queue)
    monkeypatch.setattr(knowledge_service, "get_embedder", lambda: FakeEmbedder())
    vector_store = FakeVectorStore()
    monkeypatch.setattr(knowledge_service, "get_vector_store", lambda: vector_store)

    original_vault = tmp_path / "Operator Vault"
    original_vault.mkdir()
    original_note = original_vault / "First Note.md"
    original_content = (
        b"---\ntitle: First Note\ntags: [review]\n---\n# First Note\n\n"
        b"Initial selected content. See [[Related]]."
    )
    original_note.write_bytes(original_content)
    original_target = original_vault / "Related.md"
    original_target.write_text("# Related\n", encoding="utf-8")
    response = await client.post(
        "/api/v1/knowledge/sources/obsidian-vault",
        headers={**admin_headers, "Origin": "tauri://localhost"},
        data={
            "name": "Incremental vault",
            "trust_level": "internal",
            "verification_status": "unverified",
        },
        files=[
            ("files", ("First Note.md", original_content, "text/markdown")),
            ("files", ("Related.md", b"# Related\n", "text/markdown")),
        ],
    )
    assert response.status_code == 202
    source_id = response.json()["id"]
    source = await db.get(KnowledgeSource, source_id)
    assert source is not None
    first = await source_service.sync_knowledge_source(db, source.id)
    assert first["indexed"] == 2
    documents = (
        (
            await db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.source_id == source.id
                )
            )
        )
        .scalars()
        .all()
    )
    first_id = next(
        item.id for item in documents if item.relative_name == "First Note.md"
    )
    initial_relation = (
        await db.execute(
            select(KnowledgeLink).where(KnowledgeLink.source_document_id == first_id)
        )
    ).scalar_one()
    assert initial_relation.target_name == "Related"
    assert initial_relation.resolved is True
    await db.commit()

    unchanged = await source_service.sync_knowledge_source(db, source.id)
    assert unchanged["unchanged"] == 2
    await db.commit()

    renamed = await client.post(
        f"/api/v1/knowledge/sources/{source.id}/upload",
        headers={**admin_headers, "Origin": "tauri://localhost"},
        files=[
            ("files", ("Renamed Note.md", original_content, "text/markdown")),
            ("files", ("Related.md", b"# Related\n", "text/markdown")),
        ],
    )
    assert renamed.status_code == 202
    await db.refresh(source)
    renamed_result = await source_service.sync_knowledge_source(db, source.id)
    assert renamed_result["indexed"] == 1, (
        renamed_result,
        source.metadata_json,
        source.status,
        source.error_summary,
    )
    docs_after_rename = (
        (
            await db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.source_id == source.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(docs_after_rename) == 2
    assert (
        next(
            item
            for item in docs_after_rename
            if item.relative_name == "Renamed Note.md"
        ).id
        == first_id
    )
    await db.commit()

    changed_content = b"# Updated Note\n\nChanged content with [[Related]]."
    added_content = b"# New\n\nNew local document."
    update = await client.post(
        f"/api/v1/knowledge/sources/{source.id}/upload",
        headers={**admin_headers, "Origin": "tauri://localhost"},
        files=[
            ("files", ("Renamed Note.md", changed_content, "text/markdown")),
            ("files", ("New.md", added_content, "text/markdown")),
        ],
    )
    assert update.status_code == 202
    await db.refresh(source)
    updated = await source_service.sync_knowledge_source(db, source.id)
    assert updated["indexed"] == 2
    docs_after_change = (
        (
            await db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.source_id == source.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert {item.relative_name for item in docs_after_change} == {
        "Renamed Note.md",
        "New.md",
    }
    assert (
        next(item for item in docs_after_change if item.id == first_id).content
        == changed_content.decode()
    )
    relation = (
        await db.execute(
            select(KnowledgeLink).where(KnowledgeLink.source_document_id == first_id)
        )
    ).scalar_one()
    assert relation.target_name == "Related"
    assert relation.resolved is False
    await db.commit()

    delete_stale = await client.post(
        f"/api/v1/knowledge/sources/{source.id}/upload",
        headers={**admin_headers, "Origin": "tauri://localhost"},
        files=[("files", ("Renamed Note.md", changed_content, "text/markdown"))],
    )
    assert delete_stale.status_code == 202
    await db.refresh(source)
    deleted = await source_service.sync_knowledge_source(db, source.id)
    assert deleted["deleted"] == 1
    final_docs = (
        (
            await db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.source_id == source.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert [item.relative_name for item in final_docs] == ["Renamed Note.md"]
    assert original_note.read_bytes() == original_content
    assert original_target.read_text(encoding="utf-8") == "# Related\n"
    await db.commit()

    snapshot_path = source.root_path
    removed = await client.delete(
        f"/api/v1/knowledge/sources/{source.id}", headers=admin_headers
    )
    assert removed.status_code == 204
    assert original_note.read_bytes() == original_content
    assert original_target.read_text(encoding="utf-8") == "# Related\n"
    assert snapshot_path is not None and not Path(snapshot_path).exists()


async def test_source_metadata_update_propagates_and_search_remains_local(
    monkeypatch,
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    tmp_path,
) -> None:
    from app.api.v1 import knowledge as knowledge_api
    from app.core.config import settings
    from app.models.knowledge_source import KnowledgeSource
    from app.services.knowledge import knowledge_service, source_service

    def import_root():
        root = tmp_path / "metadata-imports"
        root.mkdir(exist_ok=True)
        return root

    async def no_queue(*_args, **_kwargs):
        return None

    monkeypatch.setattr(source_service, "import_root", import_root)
    monkeypatch.setattr(
        knowledge_api, "settings_native_jobs_unavailable", lambda: False
    )
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", "desktop")
    monkeypatch.setattr(knowledge_api, "_queue_source_sync", no_queue)
    monkeypatch.setattr(knowledge_service, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(knowledge_service, "get_vector_store", FakeVectorStore)
    created = await client.post(
        "/api/v1/knowledge/sources/upload",
        headers={**admin_headers, "Origin": "tauri://localhost"},
        data={"name": "Reviewed source", "publisher": "Local Lab", "category": "Other"},
        files=[
            (
                "files",
                ("review.md", b"# Review\n\nLocal keyword reference.", "text/markdown"),
            )
        ],
    )
    assert created.status_code == 202
    source_id = created.json()["id"]
    source = await db.get(KnowledgeSource, source_id)
    assert source is not None and source.verification_status == "unverified"
    sync_result = await source_service.sync_knowledge_source(db, source.id)
    assert sync_result["indexed"] == 1
    await db.commit()
    await db.commit()

    changed = await client.patch(
        f"/api/v1/knowledge/sources/{source.id}",
        headers=admin_headers,
        json={
            "category": "Incident Response",
            "trust_level": "trusted",
            "verification_status": "reviewed",
        },
    )
    assert changed.status_code == 200
    documents = (
        (
            await db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.source_id == source.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert documents[0].category == "Incident Response"
    assert documents[0].trust_level == "trusted"
    assert documents[0].verification_status == "reviewed"
    from app.models.audit_log import AuditLog

    audit_actions = (await db.execute(select(AuditLog.action))).scalars().all()
    assert "knowledge.category_changed" in audit_actions
    assert "knowledge.trust_changed" in audit_actions
    assert "knowledge.verification_changed" in audit_actions
    found = await client.get(
        "/api/v1/knowledge/search",
        headers=admin_headers,
        params={
            "q": "local keyword",
            "mode": "keyword",
            "category": "Incident Response",
            "trust_level": "trusted",
        },
    )
    assert found.status_code == 200
    assert any(item["source_id"] == source_id for item in found.json()["items"])
    operations = await client.get("/api/v1/operations/status", headers=admin_headers)
    assert operations.status_code == 200
    index_status = operations.json()["knowledge_index"]
    assert index_status["sources"] == 1
    assert index_status["documents"] == 1
    assert "content" not in index_status


async def test_native_vault_sync_uses_private_root_and_preserves_index_while_offline(
    monkeypatch,
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    tmp_path,
) -> None:
    from app.api.v1 import knowledge as knowledge_api
    from app.core.config import settings
    from app.models.knowledge_source import KnowledgeSource
    from app.services.knowledge import knowledge_service, source_service

    def import_root():
        root = tmp_path / "live-vault-imports"
        root.mkdir(exist_ok=True)
        return root

    async def no_queue(*_args, **_kwargs):
        return None

    monkeypatch.setattr(source_service, "import_root", import_root)
    monkeypatch.setattr(
        knowledge_api, "settings_native_jobs_unavailable", lambda: False
    )
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", "desktop")
    monkeypatch.setattr(knowledge_api, "_queue_source_sync", no_queue)
    monkeypatch.setattr(knowledge_service, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(knowledge_service, "get_vector_store", FakeVectorStore)

    vault = tmp_path / "My Obsidian Vault"
    vault.mkdir()
    note = vault / "Nested" / "Network Notes.md"
    note.parent.mkdir()
    note.write_text("# Network Notes\n\nFirst version.", encoding="utf-8")
    response = await client.post(
        "/api/v1/knowledge/sources/obsidian-vault",
        headers={**admin_headers, "Origin": "tauri://localhost"},
        data={"name": "Live local vault", "source_root_path": str(vault.resolve())},
        files=[
            ("files", ("Nested/Network Notes.md", note.read_bytes(), "text/markdown"))
        ],
    )
    assert response.status_code == 202
    assert str(vault.resolve()) not in response.text
    source = await db.get(KnowledgeSource, response.json()["id"])
    assert source is not None
    assert source.local_root_path == str(vault.resolve())
    assert str(vault.resolve()) not in str(response.json())

    first = await source_service.sync_knowledge_source(db, source.id)
    assert first["indexed"] == 1
    document = (
        await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.source_id == source.id)
        )
    ).scalar_one()
    document_id = document.id
    assert document.content.endswith("First version.")
    await db.commit()

    note.write_text("# Network Notes\n\nUpdated version.", encoding="utf-8")
    changed = await source_service.sync_knowledge_source(db, source.id)
    assert changed["indexed"] == 1
    document = await db.get(KnowledgeDocument, document_id)
    assert document is not None and document.content.endswith("Updated version.")
    await db.commit()

    import shutil

    shutil.rmtree(vault)
    offline = await source_service.sync_knowledge_source(db, source.id)
    assert offline["offline"] is True
    preserved = await db.get(KnowledgeDocument, document_id)
    assert preserved is not None and preserved.content.endswith("Updated version.")
    assert source.status == "offline"
    await db.commit()

    relinked_vault = tmp_path / "Relinked Vault"
    relinked_vault.mkdir()
    relinked_note = relinked_vault / "Nested" / "Network Notes.md"
    relinked_note.parent.mkdir()
    relinked_note.write_text("# Network Notes\n\nRelinked version.", encoding="utf-8")
    relink_response = await client.post(
        f"/api/v1/knowledge/sources/{source.id}/upload",
        headers={**admin_headers, "Origin": "tauri://localhost"},
        data={"source_root_path": str(relinked_vault.resolve())},
        files=[
            (
                "files",
                (
                    "Nested/Network Notes.md",
                    relinked_note.read_bytes(),
                    "text/markdown",
                ),
            )
        ],
    )
    assert relink_response.status_code == 202
    assert str(relinked_vault.resolve()) not in relink_response.text
    await db.refresh(source)
    assert source.local_root_path == str(relinked_vault.resolve())
    relink_result = await source_service.sync_knowledge_source(db, source.id)
    assert relink_result["indexed"] == 1
    document = await db.get(KnowledgeDocument, document_id)
    assert document is not None and document.content.endswith("Relinked version.")


async def test_analyst_cannot_manage_knowledge_sources(
    client: AsyncClient,
    analyst_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/v1/knowledge/sources/obsidian-vault",
        headers={**analyst_headers, "Origin": "tauri://localhost"},
        data={"name": "Not allowed"},
        files=[("files", ("note.md", b"# note", "text/markdown"))],
    )
    assert response.status_code == 403


async def test_knowledge_search_keyword_semantic_and_hybrid(
    monkeypatch,
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    tmp_path,
) -> None:
    from app.api.v1 import knowledge as knowledge_api
    from app.core.config import settings
    from app.models.knowledge_source import KnowledgeSource
    from app.services.knowledge import knowledge_service, source_service

    def import_root():
        root = tmp_path / "imports"
        root.mkdir(exist_ok=True)
        return root

    async def no_queue(*_args, **_kwargs):
        return None

    monkeypatch.setattr(source_service, "import_root", import_root)
    monkeypatch.setattr(
        knowledge_api, "settings_native_jobs_unavailable", lambda: False
    )
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", "desktop")
    monkeypatch.setattr(knowledge_api, "_queue_source_sync", no_queue)
    fake_store = FakeVectorStore()
    monkeypatch.setattr(knowledge_service, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(knowledge_service, "get_vector_store", lambda: fake_store)
    source_response = await client.post(
        "/api/v1/knowledge/sources/obsidian-vault",
        headers={**admin_headers, "Origin": "tauri://localhost"},
        data={
            "name": "IR notes",
            "trust_level": "internal",
            "verification_status": "unverified",
        },
        files=[
            (
                "files",
                (
                    "ir.md",
                    b"# Incident Response\n\nContain malware quickly. #ir\n",
                    "text/markdown",
                ),
            )
        ],
    )
    assert source_response.status_code == 202
    source = await db.get(KnowledgeSource, source_response.json()["id"])
    assert source is not None
    sync_result = await source_service.sync_knowledge_source(db, source.id)
    assert sync_result["indexed"] == 1
    await db.commit()

    for mode in ("keyword", "semantic", "hybrid"):
        response = await client.get(
            "/api/v1/knowledge/search",
            headers=admin_headers,
            params={"q": "malware", "mode": mode, "source_id": str(source.id)},
        )
        assert response.status_code == 200
        assert response.json()["items"]
        assert response.json()["items"][0]["title"] == "Incident Response"
