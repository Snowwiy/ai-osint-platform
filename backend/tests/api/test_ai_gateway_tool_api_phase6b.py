from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.api.v1 import ai_gateway
from app.core.security import create_access_token
from app.services.ai import tool_gateway
from app.services.ai.opencode_adapter import ModelRecord


class SyntheticToolAdapter:
    def __init__(self, *, ask_for_tool: bool = True, ask_twice: bool = False) -> None:
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
        self.prompts: list[str] = []
        self.ask_for_tool = ask_for_tool
        self.ask_twice = ask_twice

    async def get_runtime(self):
        return {"available": True, "status": "available", "message": "fixture"}

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

    async def create_session(self, _title: str) -> str:
        return "phase6b-synthetic-session"

    async def complete(self, _session_id, _provider_id, _model_id, prompt: str) -> str:
        self.prompts.append(prompt)
        if "Registered tools for this user:" in prompt and self.ask_for_tool:
            return (
                '<raventech_tool_request>{"tool_calls":[{"tool":'
                '"raventech.host.summary","arguments":{}}]}'
                "</raventech_tool_request>"
            )
        if self.ask_twice and "Bounded structured RavenTech evidence" in prompt:
            return (
                '<raventech_tool_request>{"tool_calls":[{"tool":'
                '"raventech.host.summary","arguments":{}}]}'
                "</raventech_tool_request>"
            )
        return "RavenTech Fact: the synthetic host snapshot reports 12 percent CPU."

    async def complete_local(self, _provider_id, _model_id, _prompt):
        return "Local fixture response."

    async def cancel(self, _session_id: str) -> bool:
        return True

    async def close_session(self, _session_id: str) -> bool:
        return True


def _install_adapter(monkeypatch, adapter: SyntheticToolAdapter) -> None:
    monkeypatch.setattr(ai_gateway, "get_adapter", lambda: adapter)


@pytest.mark.asyncio
async def test_tool_catalog_is_authenticated_role_filtered_and_read_only(
    client, analyst_headers, admin_headers
):
    analyst = await client.get("/api/v1/ai/tools", headers=analyst_headers)
    admin = await client.get("/api/v1/ai/tools", headers=admin_headers)
    assert analyst.status_code == admin.status_code == 200
    assert analyst.json()["write_count"] == admin.json()["write_count"] == 0
    assert analyst.json()["shell_available"] is False
    assert analyst.json()["sql_available"] is False
    assert analyst.json()["filesystem_available"] is False
    assert all(item["read_only"] for item in admin.json()["items"])
    assert len(admin.json()["items"]) == 18
    assert len(analyst.json()["items"]) < len(admin.json()["items"])


@pytest.mark.asyncio
async def test_execute_endpoint_denies_unknown_and_admin_only_tools_safely(
    client, analyst_headers
):
    unknown = await client.post(
        "/api/v1/ai/tools/execute",
        headers=analyst_headers,
        json={"tool_id": "shell-password=do-not-echo", "arguments": {}},
    )
    assert unknown.status_code == 200
    assert unknown.json()["safe_error_code"] == "unknown_tool"
    assert "do-not-echo" not in unknown.text
    denied = await client.post(
        "/api/v1/ai/tools/execute",
        headers=analyst_headers,
        json={"tool_id": "raventech.host.processes.list", "arguments": {}},
    )
    assert denied.status_code == 200
    assert denied.json()["safe_error_code"] == "authorization_denied"


@pytest.mark.parametrize(
    "tool_id",
    [
        "shell.run",
        "powershell.execute",
        "raventech.sql.query",
        "raventech.files.read",
        "raventech.config.write",
        "http.request",
        "service.control",
        "process.terminate",
        "ssh.execute",
    ],
)
@pytest.mark.asyncio
async def test_prohibited_capability_classes_are_not_registered(
    client, admin_headers, monkeypatch, tool_id
):
    async def forbidden_handler(*_args, **_kwargs):
        raise AssertionError("unregistered capability reached a handler")

    monkeypatch.setattr(tool_gateway, "_handle_tool", forbidden_handler)
    response = await client.post(
        "/api/v1/ai/tools/execute",
        headers=admin_headers,
        json={"tool_id": tool_id, "arguments": {}},
    )
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["safe_error_code"] == "unknown_tool"
    assert response.json()["tool"] == "raventech"


@pytest.mark.asyncio
async def test_remote_tool_evidence_requires_turn_specific_consent(
    client, analyst_headers, monkeypatch
):
    adapter = SyntheticToolAdapter(ask_for_tool=False)
    _install_adapter(monkeypatch, adapter)

    async def forbidden_handler(*_args, **_kwargs):
        raise AssertionError("remote evidence was executed without consent")

    monkeypatch.setattr(tool_gateway, "_handle_tool", forbidden_handler)
    created = await client.post(
        "/api/v1/ai/sessions",
        headers=analyst_headers,
        json={"model_id": "fixture/free-model", "title": "No remote consent"},
    )
    assert created.status_code == 201, created.text
    response = await client.post(
        f"/api/v1/ai/sessions/{created.json()['id']}/messages",
        headers=analyst_headers,
        json={"content": "Analyze the server", "workflow": "analyze_server"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["assistant_message"]["content"] == (
        "RavenTech Fact: the synthetic host snapshot reports 12 percent CPU."
    )
    assert len(adapter.prompts) == 1
    assert "Bounded structured RavenTech evidence" not in adapter.prompts[0]


@pytest.mark.asyncio
async def test_model_tool_call_executes_once_and_persists_activity_and_evidence(
    client, analyst_headers, monkeypatch
):
    adapter = SyntheticToolAdapter(ask_twice=True)
    _install_adapter(monkeypatch, adapter)
    executions = 0

    async def evidence_handler(*_args, **_kwargs):
        nonlocal executions
        executions += 1
        return (
            {"cpu_percent": 12, "available": True},
            [
                {
                    "id": "HOST-METRIC:phase6b-fixture",
                    "source_type": "host-metric",
                    "confidence": "high",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "scope": {"type": "primary_host"},
                }
            ],
            [],
            {"type": "primary_host"},
        )

    monkeypatch.setattr(tool_gateway, "_handle_tool", evidence_handler)
    created = await client.post(
        "/api/v1/ai/sessions",
        headers=analyst_headers,
        json={"model_id": "fixture/free-model", "title": "Tool call test"},
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]
    response = await client.post(
        f"/api/v1/ai/sessions/{session_id}/messages",
        headers=analyst_headers,
        json={
            "content": "Review current CPU evidence",
            "allow_remote_tool_context": True,
        },
    )
    assert response.status_code == 200, response.text
    assert executions == 1
    assert (
        "tool request limit was reached"
        in response.json()["assistant_message"]["content"]
    )
    session = await client.get(
        f"/api/v1/ai/sessions/{session_id}", headers=analyst_headers
    )
    assert session.status_code == 200
    payload = session.json()
    user_message = next(item for item in payload["messages"] if item["role"] == "user")
    activity = [
        item
        for item in user_message["context_sources"]
        if item["kind"] == "tool_activity"
    ]
    assert activity[0]["tool_id"] == "raventech.host.summary"
    reference = activity[0]["evidence_references"][0]
    assert reference["id"] == "HOST-METRIC:phase6b-fixture"
    assert reference["source_type"] == "host-metric"
    assert reference["confidence"] == "high"
    assert reference["scope"] == {"type": "primary_host"}
    assert "HOST-METRIC:phase6b-fixture" in user_message["supplied_citations"]
    assert payload["tool_activity"]


@pytest.mark.asyncio
async def test_investigation_tool_respects_membership(
    client, analyst_user, other_user, analyst_headers, test_investigation
):
    token = create_access_token(user_id=str(other_user.id), role=other_user.role)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post(
        "/api/v1/ai/tools/execute",
        headers=headers,
        json={
            "tool_id": "raventech.investigation.get",
            "arguments": {"investigation_id": str(test_investigation.id)},
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["safe_error_code"] == "not_found"


@pytest.mark.asyncio
async def test_registered_tool_handlers_return_bounded_envelopes(
    client, admin_headers
):
    asset_id = uuid.uuid4()
    investigation_id = uuid.uuid4()
    inventory = {
        "available": True,
        "processes": [
            {
                "pid": 444,
                "name": "raventech-worker.exe",
                "cpuPercent": 1.5,
                "memoryBytes": 2048,
                "startedAtUnix": 1,
                "runtimeSeconds": 10,
            }
        ],
        "services": [
            {
                "name": "RavenTechWorker",
                "displayName": "RavenTech Worker",
                "state": "running",
                "startType": "automatic",
                "pid": 444,
            }
        ],
    }
    calls = [
        ("raventech.host.summary", {}),
        ("raventech.host.metrics", {"window": "15m"}),
        ("raventech.host.processes.list", {"limit": 10}),
        ("raventech.host.services.list", {"limit": 10}),
        ("raventech.host.listening_ports", {"limit": 10}),
        ("raventech.lan.summary", {}),
        ("raventech.lan.assets.list", {"limit": 10}),
        ("raventech.lan.asset.get", {"asset_id": str(asset_id)}),
        ("raventech.endpoint.summary", {}),
        ("raventech.endpoint.get", {"asset_id": str(asset_id)}),
        ("raventech.security.posture", {"scope": "global"}),
        ("raventech.alerts.list", {"limit": 10}),
        ("raventech.timeline.list", {"limit": 10}),
        (
            "raventech.knowledge.search",
            {"query": "synthetic safety guidance", "top_k": 3},
        ),
        ("raventech.investigations.list", {"limit": 10}),
        (
            "raventech.investigation.get",
            {"investigation_id": str(investigation_id)},
        ),
        (
            "raventech.findings.list",
            {"investigation_id": str(investigation_id), "limit": 10},
        ),
        ("raventech.operations.summary", {}),
    ]
    for tool_id, arguments in calls:
        body = {"tool_id": tool_id, "arguments": arguments}
        if tool_id in {
            "raventech.host.processes.list",
            "raventech.host.services.list",
        }:
            body["desktop_inventory"] = inventory
        response = await client.post(
            "/api/v1/ai/tools/execute", headers=admin_headers, json=body
        )
        assert response.status_code == 200, (tool_id, response.text)
        envelope = response.json()
        assert envelope["tool"] in {tool_id, "raventech"}
        assert "success" in envelope
        assert "generated_at" in envelope
        assert len(response.content) < 64_000
        assert "DATABASE_URL=" not in response.text
        assert "command_line" not in response.text
