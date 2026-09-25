from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import pytest
from app.api.v1 import ai_gateway
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.ai.opencode_adapter import ModelRecord
from sqlalchemy import select


class FakeOpenCodeAdapter:
    def __init__(self) -> None:
        self.model = ModelRecord(
            id="fixture/free-model",
            provider_id="fixture",
            model_id="free-model",
            display_name="Synthetic free test model",
            available=True,
            local=False,
            remote=True,
            free_status="provider_reported_free",
            context_window=4096,
            supports_tools=True,
            supports_vision=None,
            supports_reasoning=None,
            supports_streaming=True,
            metadata_source="deterministic test fixture",
            last_discovered_at=datetime.now(UTC),
        )
        self.stream_started = asyncio.Event()
        self.block_stream = False
        self.last_prompt = ""
        self.cancel_called = False

    async def get_runtime(self):
        return {
            "available": True,
            "status": "available",
            "version": "test",
            "loopback_only": True,
            "message": "fixture available",
        }

    async def discover(self, *, refresh: bool = False):
        return [
            {
                "id": "fixture",
                "name": "Fixture",
                "category": "other",
                "connected": True,
                "local": False,
                "remote": True,
                "status": "connected",
            }
        ], [self.model]

    async def create_session(self, title: str) -> str:
        return "test-session-123"

    async def complete(
        self, session_id: str, provider_id: str, model_id: str, prompt: str
    ) -> str:
        self.last_prompt = prompt
        return "READY. Evidence is limited."

    async def complete_local(self, provider_id: str, model_id: str, prompt: str) -> str:
        self.last_prompt = prompt
        return "READY."

    async def stream_complete(
        self, session_id, provider_id, model_id, prompt, cancel_event
    ):
        self.last_prompt = prompt
        self.stream_started.set()
        yield "Evidence "
        if self.block_stream:
            await cancel_event.wait()
        if not cancel_event.is_set():
            yield "reviewed."

    async def stream_local(self, provider_id, model_id, prompt, cancel_event):
        self.last_prompt = prompt
        yield "Local response"

    async def cancel(self, session_id: str) -> bool:
        self.cancel_called = True
        return True

    async def close_session(self, session_id: str) -> bool:
        return True


def _install_adapter(monkeypatch, adapter: FakeOpenCodeAdapter) -> None:
    monkeypatch.setattr(ai_gateway, "get_adapter", lambda: adapter)


@pytest.mark.asyncio
async def test_model_catalog_preferences_and_paid_policy(
    client, analyst_headers, monkeypatch
):
    adapter = FakeOpenCodeAdapter()
    _install_adapter(monkeypatch, adapter)
    catalog = await client.get("/api/v1/ai/models", headers=analyst_headers)
    assert catalog.status_code == 200
    assert catalog.json()["recommended_model_id"] == "fixture/free-model"
    assert catalog.json()["models"][0]["free_status"] == "provider_reported_free"
    preferences = await client.put(
        "/api/v1/ai/preferences",
        headers=analyst_headers,
        json={
            "execution_mode": "local_only",
            "selected_model_id": "fixture/free-model",
        },
    )
    assert preferences.status_code == 403
    saved = await client.put(
        "/api/v1/ai/preferences",
        headers=analyst_headers,
        json={
            "execution_mode": "free_only",
            "selected_model_id": "fixture/free-model",
        },
    )
    assert saved.status_code == 200


@pytest.mark.asyncio
async def test_streaming_session_persists_sanitized_user_visible_messages(
    client, analyst_headers, db, monkeypatch
):
    adapter = FakeOpenCodeAdapter()
    _install_adapter(monkeypatch, adapter)
    created = await client.post(
        "/api/v1/ai/sessions",
        headers=analyst_headers,
        json={"model_id": "fixture/free-model", "title": "Test chat"},
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]
    response = await client.post(
        f"/api/v1/ai/sessions/{session_id}/messages/stream",
        headers=analyst_headers,
        json={"content": "Review this note: password=acceptance-secret"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    delta_text = "".join(
        json.loads(line.removeprefix("data: "))["text"]
        for block in response.text.split("\n\n")
        if block.startswith("event: delta\n")
        for line in block.splitlines()
        if line.startswith("data: ")
    )
    assert delta_text == "Evidence reviewed."
    assert "event: done" in response.text
    assert "acceptance-secret" not in adapter.last_prompt
    session = await client.get(
        f"/api/v1/ai/sessions/{session_id}", headers=analyst_headers
    )
    assert session.status_code == 200
    messages = session.json()["messages"]
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert "acceptance-secret" not in messages[0]["content"]
    assert messages[1]["status"] == "completed"
    actions = (
        (
            await db.execute(
                select(AuditLog.action).where(AuditLog.action.like("ai.message_%"))
            )
        )
        .scalars()
        .all()
    )
    assert "ai.message_requested" in actions
    assert "ai.message_completed" in actions


@pytest.mark.asyncio
async def test_streaming_redacts_sensitive_value_split_across_provider_chunks(
    client, analyst_headers, monkeypatch
):
    adapter = FakeOpenCodeAdapter()

    async def split_secret_stream(
        session_id, provider_id, model_id, prompt, cancel_event
    ):
        yield "Visible explanation. "
        yield "api_key=sk-proj-"
        yield "split-secret-value"
        yield " next step."

    adapter.stream_complete = split_secret_stream
    _install_adapter(monkeypatch, adapter)
    created = await client.post(
        "/api/v1/ai/sessions",
        headers=analyst_headers,
        json={"model_id": "fixture/free-model", "title": "Redaction test"},
    )
    response = await client.post(
        f"/api/v1/ai/sessions/{created.json()['id']}/messages/stream",
        headers=analyst_headers,
        json={"content": "Explain this synthetic example"},
    )
    delta_text = "".join(
        json.loads(line.removeprefix("data: "))["text"]
        for block in response.text.split("\n\n")
        if block.startswith("event: delta\n")
        for line in block.splitlines()
        if line.startswith("data: ")
    )
    assert response.status_code == 200
    assert "split-secret-value" not in delta_text
    assert "sk-proj" not in delta_text
    assert "api_key=[REDACTED]" in delta_text
    assert "next step" in delta_text


@pytest.mark.asyncio
async def test_stream_cancel_is_cooperative_and_owner_scoped(
    client, analyst_headers, analyst_user, db, monkeypatch
):
    adapter = FakeOpenCodeAdapter()
    adapter.block_stream = True
    _install_adapter(monkeypatch, adapter)
    created = await client.post(
        "/api/v1/ai/sessions",
        headers=analyst_headers,
        json={"model_id": "fixture/free-model", "title": "Cancelable"},
    )
    session_id = created.json()["id"]
    stream_task = asyncio.create_task(
        client.post(
            f"/api/v1/ai/sessions/{session_id}/messages/stream",
            headers=analyst_headers,
            json={"content": "Explain the test finding"},
        )
    )
    await asyncio.wait_for(adapter.stream_started.wait(), timeout=2)
    cancelled = await client.post(
        f"/api/v1/ai/sessions/{session_id}/cancel", headers=analyst_headers
    )
    result = await asyncio.wait_for(stream_task, timeout=2)
    assert cancelled.status_code == 200 and cancelled.json()["cancelled"] is True
    assert adapter.cancel_called is True
    assert '"status": "cancelled"' in result.text
    session = await client.get(
        f"/api/v1/ai/sessions/{session_id}", headers=analyst_headers
    )
    assert session.json()["status"] == "cancelled"

    other = User(
        username="second_ai_analyst",
        email="second-ai-analyst@test.raventech.mx",
        hashed_password="not-used",
        role="analyst",
        is_active=True,
    )
    db.add(other)
    await db.commit()
    from app.core.security import create_access_token

    other_token = create_access_token(user_id=str(other.id), role=other.role)
    other_headers = {"Authorization": f"Bearer {other_token}"}
    hidden = await client.get(
        f"/api/v1/ai/sessions/{session_id}", headers=other_headers
    )
    assert hidden.status_code == 404


@pytest.mark.asyncio
async def test_model_test_is_admin_only_and_handoff_is_copy_only(
    client, analyst_headers, admin_headers, db, monkeypatch
):
    adapter = FakeOpenCodeAdapter()
    _install_adapter(monkeypatch, adapter)
    denied = await client.post(
        "/api/v1/ai/models/test",
        headers=analyst_headers,
        json={"model_id": "fixture/free-model"},
    )
    assert denied.status_code == 403
    tested = await client.post(
        "/api/v1/ai/models/test",
        headers=admin_headers,
        json={"model_id": "fixture/free-model"},
    )
    assert tested.status_code == 200 and tested.json()["available"] is True
    handoff = await client.post(
        "/api/v1/ai/prompt-handoff",
        headers=analyst_headers,
        json={
            "kind": "investigation",
            "title": "Synthetic case",
            "facts": {"Observation": "Only a passive DNS record was observed"},
            "citations": ["finding:synthetic-01"],
            "model_id": "fixture/free-model",
        },
    )
    assert handoff.status_code == 200
    payload = handoff.json()
    assert "finding:synthetic-01" in payload["prompt"]
    assert "opencode run" in payload["command"]
    for kind in ("recommendation", "asset"):
        typed_handoff = await client.post(
            "/api/v1/ai/prompt-handoff",
            headers=analyst_headers,
            json={
                "kind": kind,
                "title": f"Synthetic {kind}",
                "facts": {"Observation": "A synthetic private test record"},
                "citations": [f"{kind}:synthetic-01"],
                "model_id": "fixture/free-model",
            },
        )
        assert typed_handoff.status_code == 200
        assert f"{kind}:synthetic-01" in typed_handoff.json()["prompt"]
    copied = await client.post(
        "/api/v1/ai/prompt-handoff/copied",
        headers=analyst_headers,
        json={"content_hash": payload["content_hash"], "content_type": "command"},
    )
    assert copied.status_code == 204
    audit = (
        (
            await db.execute(
                select(AuditLog).where(AuditLog.action == "ai.prompt_copied")
            )
        )
        .scalars()
        .all()
    )
    assert audit and all(
        "Observation" not in str(item.event_metadata) for item in audit
    )


@pytest.mark.asyncio
async def test_operations_ai_status_is_admin_only_and_contains_no_provider_secrets(
    client, analyst_headers, admin_headers, monkeypatch
):
    adapter = FakeOpenCodeAdapter()
    _install_adapter(monkeypatch, adapter)
    denied = await client.get("/api/v1/ai/operations-status", headers=analyst_headers)
    assert denied.status_code == 403
    response = await client.get("/api/v1/ai/operations-status", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["dependency"] == "optional"
    assert payload["available_models"] == 1
    assert "api_key" not in str(payload).casefold()


@pytest.mark.asyncio
async def test_session_count_is_bounded_and_running_session_is_protected(
    client, analyst_headers, monkeypatch, db
):
    adapter = FakeOpenCodeAdapter()
    _install_adapter(monkeypatch, adapter)
    monkeypatch.setattr(ai_gateway.settings, "AI_SESSION_MAX_SESSIONS", 1)
    created = await client.post(
        "/api/v1/ai/sessions",
        headers=analyst_headers,
        json={"model_id": "fixture/free-model", "title": "Bounded session"},
    )
    assert created.status_code == 201
    second = await client.post(
        "/api/v1/ai/sessions",
        headers=analyst_headers,
        json={"model_id": "fixture/free-model", "title": "Over limit"},
    )
    assert second.status_code == 409

    from app.models.ai_session import AiSession

    session_id = created.json()["id"]
    session = await db.get(AiSession, session_id)
    assert session is not None
    session.status = "running"
    await db.commit()
    archived = await client.post(
        f"/api/v1/ai/sessions/{session_id}/archive", headers=analyst_headers
    )
    deleted = await client.delete(
        f"/api/v1/ai/sessions/{session_id}", headers=analyst_headers
    )
    assert archived.status_code == 409
    assert deleted.status_code == 409
