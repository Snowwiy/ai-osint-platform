from __future__ import annotations

import asyncio
import socket
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from app.api.v1.ai_gateway import (
    _automatic_local_model,
    _catalog,
    _resolve_message_model,
    _test_local_model_capabilities,
)
from app.core.config import settings
from app.models.ai_session import AiSession
from app.schemas.ai_gateway import AiMessageRequest, AiPreferences
from app.services.ai.benchmark import _synthetic_cases, run_local_benchmark
from app.services.ai.gateway_service import require_allowed_model
from app.services.ai.hardware_profile import (
    collect_hardware_profile,
    evaluate_model_fit,
)
from app.services.ai.local_runtime import (
    RuntimeDefinition,
    _normalize_models,
    _probe,
    configured_runtime_definitions,
    safe_loopback_endpoint,
)
from app.services.ai.opencode_adapter import LocalOpenCodeAdapter, ModelRecord


def test_loopback_endpoint_accepts_ipv4_ipv6_and_resolved_localhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert safe_loopback_endpoint("http://127.0.0.1:11434") == (
        "http://127.0.0.1:11434"
    )
    assert safe_loopback_endpoint("http://[::1]:8080/v1") == "http://[::1]:8080/v1"
    monkeypatch.setattr(
        "app.services.ai.local_runtime.socket.getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 1234)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 1234, 0, 0)),
        ],
    )
    assert safe_loopback_endpoint("http://localhost:1234") == ("http://127.0.0.1:1234")


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://192.168.1.10:11434",
        "http://8.8.8.8:11434",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "http://user:password@127.0.0.1:11434",
        "http://127.0.0.1:11434/?token=secret",
        "http://0.0.0.0:11434",
    ],
)
def test_loopback_endpoint_rejects_network_and_credential_destinations(
    endpoint: str,
) -> None:
    with pytest.raises(ValueError):
        safe_loopback_endpoint(endpoint)


def test_localhost_dns_rebinding_to_lan_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.ai.local_runtime.socket.getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.9", 80))
        ],
    )
    with pytest.raises(ValueError, match="resolved outside loopback"):
        safe_loopback_endpoint("http://localhost:11434")


@pytest.mark.asyncio
async def test_explicit_network_runtime_is_classified_and_blocked() -> None:
    result = await _probe(
        RuntimeDefinition(
            provider_id="llamacpp",
            name="llama.cpp",
            endpoint="http://192.168.1.20:8080",
            kind="openai",
            configured=True,
        )
    )
    assert result.runtime.status == "incompatible"
    assert result.runtime.endpoint_classification == "network"
    assert result.runtime.loopback_only is False
    assert result.provider["local"] is False
    assert result.provider["remote"] is True


@pytest.mark.asyncio
async def test_ollama_probe_uses_reported_inventory_and_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    original_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "fixture",
                            "size": 2_000_000_000,
                            "details": {
                                "parameter_size": "3B",
                                "quantization_level": "Q4_K_M",
                            },
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"version": "0.9.1"})

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    result = await _probe(
        RuntimeDefinition(
            provider_id="ollama",
            name="Ollama",
            endpoint="http://127.0.0.1:11434",
            kind="ollama",
            configured=True,
        )
    )
    assert calls == ["/api/tags", "/api/version"]
    assert result.runtime.status == "available"
    assert result.runtime.version == "0.9.1"
    assert result.models[0].size_bytes == 2_000_000_000
    assert result.models[0].parameter_count == 3_000_000_000
    assert result.models[0].quantization == "Q4_K_M"


@pytest.mark.parametrize(
    "provider_id", ["lmstudio", "llamacpp", "vllm", "openai_compatible_local"]
)
@pytest.mark.asyncio
async def test_openai_compatible_runtime_probe_is_provider_independent(
    provider_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    original_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(
            200,
            headers={"x-runtime-version": "fixture-1.0"},
            json={"data": [{"id": "fixture-model"}]},
        )

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    result = await _probe(
        RuntimeDefinition(
            provider_id=provider_id,
            name=provider_id,
            endpoint="http://127.0.0.1:8080/v1",
            kind="openai",
            configured=True,
        )
    )
    assert calls == ["/v1/models"]
    assert result.runtime.status == "available"
    assert result.runtime.version == "fixture-1.0"
    assert result.models[0].id == f"{provider_id}/fixture-model"
    assert result.models[0].local is True
    assert result.models[0].remote is False


@pytest.mark.parametrize(
    ("provider_id", "config_name", "endpoint", "expected_path"),
    [
        ("ollama", None, None, "/api/chat"),
        (
            "lmstudio",
            None,
            None,
            "/v1/chat/completions",
        ),
        (
            "llamacpp",
            "AI_LLAMA_CPP_ENDPOINT",
            "http://127.0.0.1:8080/v1",
            "/v1/chat/completions",
        ),
        (
            "vllm",
            "AI_VLLM_ENDPOINT",
            "http://127.0.0.1:8000/v1",
            "/v1/chat/completions",
        ),
        (
            "openai_compatible_local",
            "AI_OPENAI_COMPATIBLE_LOCAL_ENDPOINT",
            "http://127.0.0.1:9000/v1",
            "/v1/chat/completions",
        ),
    ],
)
@pytest.mark.asyncio
async def test_direct_local_completion_uses_only_loopback_runtime_contract(
    provider_id: str,
    config_name: str | None,
    endpoint: str | None,
    expected_path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if config_name and endpoint:
        monkeypatch.setattr(settings, config_name, endpoint)
    adapter = LocalOpenCodeAdapter()
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_post_json(
        url: str, payload: dict[str, object], *, timeout: float = 10.0
    ) -> dict[str, object]:
        calls.append((url, payload))
        if provider_id == "ollama":
            return {"message": {"content": "READY"}}
        return {"choices": [{"message": {"content": "READY"}}]}

    monkeypatch.setattr(adapter, "_post_json", fake_post_json)
    response = await adapter.complete_local(
        provider_id, "fixture-model", "Reply with READY only."
    )
    assert response == "READY"
    assert len(calls) == 1
    url, payload = calls[0]
    assert httpx.URL(url).path == expected_path
    assert "127.0.0.1" in url
    messages = payload["messages"]
    assert isinstance(messages, list)
    assert messages[-1] == {"role": "user", "content": "Reply with READY only."}
    assert "tool" not in payload


@pytest.mark.asyncio
async def test_offline_catalog_and_model_gate_never_call_remote_discovery() -> None:
    class OfflineAdapter:
        def __init__(self, models: list[ModelRecord]) -> None:
            self.models = models
            self.remote_discovery_count = 0
            self.local_discovery_count = 0

        async def discover(self, *, refresh: bool = False):
            self.remote_discovery_count += 1
            raise AssertionError("remote discovery must remain blocked")

        async def discover_local(self, *, refresh: bool = False):
            self.local_discovery_count += 1
            return [], self.models

    model = ModelRecord(
        id="ollama/offline-fixture",
        provider_id="ollama",
        model_id="offline-fixture",
        display_name="Offline fixture",
        available=True,
        local=True,
        remote=False,
        free_status="local",
        context_window=None,
        supports_tools=None,
        supports_vision=None,
        supports_reasoning=None,
        supports_streaming=None,
        metadata_source="test fixture",
        last_discovered_at=datetime.now(UTC),
        runtime_id="ollama",
    )
    adapter = OfflineAdapter([model])
    catalog = await _catalog(
        adapter,  # type: ignore[arg-type]
        refresh=False,
        preferences=AiPreferences(offline_ai_enabled=True),
    )
    allowed = await require_allowed_model(
        adapter,
        model.id,
        "offline",  # type: ignore[arg-type]
    )
    assert allowed.local is True
    assert catalog.runtime.integration == "Direct local runtimes"
    assert [item.id for item in catalog.models] == [model.id]
    assert catalog.models[0].installed is True
    assert adapter.remote_discovery_count == 0

    adapter.models = []
    with pytest.raises(ValueError, match="Model unavailable"):
        await require_allowed_model(
            adapter,
            model.id,
            "offline",  # type: ignore[arg-type]
        )
    assert adapter.remote_discovery_count == 0
    assert adapter.local_discovery_count == 3


@pytest.mark.asyncio
async def test_local_first_policy_blocks_paid_remote_models() -> None:
    remote = ModelRecord(
        id="fixture/paid-model",
        provider_id="fixture",
        model_id="paid-model",
        display_name="Paid fixture",
        available=True,
        local=False,
        remote=True,
        free_status="paid",
        context_window=None,
        supports_tools=None,
        supports_vision=None,
        supports_reasoning=None,
        supports_streaming=None,
        metadata_source="provider fixture",
        last_discovered_at=datetime.now(UTC),
    )

    class LocalFirstAdapter:
        async def discover(self, *, refresh: bool = False):
            return [], [remote]

    with pytest.raises(PermissionError, match="Local-first and free-only"):
        await require_allowed_model(
            LocalFirstAdapter(),  # type: ignore[arg-type]
            remote.id,
            "local_first",
        )


@pytest.mark.asyncio
async def test_automatic_local_route_uses_only_configured_local_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local = ModelRecord(
        id="ollama/triage",
        provider_id="ollama",
        model_id="triage",
        display_name="Triage fixture",
        available=True,
        local=True,
        remote=False,
        free_status="local",
        context_window=None,
        supports_tools=None,
        supports_vision=None,
        supports_reasoning=None,
        supports_streaming=None,
        metadata_source="runtime fixture",
        last_discovered_at=datetime.now(UTC),
        runtime_id="ollama",
    )
    discovery_calls: list[bool] = []

    async def local_catalog(_adapter, *, refresh: bool = False):
        discovery_calls.append(refresh)
        return [], [local]

    monkeypatch.setattr("app.api.v1.ai_gateway._discover_local_catalog", local_catalog)
    selected, reason = await _automatic_local_model(
        object(),  # type: ignore[arg-type]
        uuid.uuid4(),
        AiPreferences(
            routing_mode="automatic_local",
            task_model_routes={"fast_triage": local.id},
        ),
        "fast_triage",
    )
    assert selected is local
    assert reason == "automatic_local:fast_triage:configured_route"
    assert discovery_calls == [False]


@pytest.mark.asyncio
async def test_automatic_local_route_uses_same_hardware_benchmark_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def model(model_id: str) -> ModelRecord:
        return ModelRecord(
            id=f"ollama/{model_id}",
            provider_id="ollama",
            model_id=model_id,
            display_name=model_id,
            available=True,
            local=True,
            remote=False,
            free_status="local",
            context_window=None,
            supports_tools=None,
            supports_vision=None,
            supports_reasoning=None,
            supports_streaming=None,
            metadata_source="runtime fixture",
            last_discovered_at=datetime.now(UTC),
            runtime_id="ollama",
        )

    faster = model("faster")
    more_grounded = model("more-grounded")

    async def local_catalog(_adapter, *, refresh: bool = False):
        return [], [faster, more_grounded]

    class BenchmarkRows:
        def scalars(self):
            return self

        def all(self):
            return [
                SimpleNamespace(
                    model_id=faster.id,
                    metrics={"scores": {"basic_chat": 40.0}},
                ),
                SimpleNamespace(
                    model_id=more_grounded.id,
                    metrics={"scores": {"basic_chat": 95.0}},
                ),
            ]

    class BenchmarkDb:
        async def execute(self, _statement):
            return BenchmarkRows()

    monkeypatch.setattr("app.api.v1.ai_gateway._discover_local_catalog", local_catalog)
    monkeypatch.setattr(
        "app.api.v1.ai_gateway.evaluate_model_fit",
        lambda **_kwargs: ("good_fit", "fixture fit", 1),
    )
    selected, reason = await _automatic_local_model(
        BenchmarkDb(),  # type: ignore[arg-type]
        uuid.uuid4(),
        AiPreferences(routing_mode="automatic_local"),
        "fast_triage",
    )
    assert selected is more_grounded
    assert reason == "automatic_local:fast_triage:hardware_and_benchmark"


@pytest.mark.asyncio
async def test_automatic_local_route_fails_closed_without_local_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def local_catalog(_adapter, *, refresh: bool = False):
        return [], []

    monkeypatch.setattr("app.api.v1.ai_gateway._discover_local_catalog", local_catalog)
    session = AiSession(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        provider_id="fixture",
        model_id="remote-model",
        execution_type="remote",
    )
    with pytest.raises(ValueError, match="No remote fallback was used"):
        await _resolve_message_model(
            object(),  # type: ignore[arg-type]
            session.owner_id,
            session,
            AiPreferences(routing_mode="automatic_local"),
            AiMessageRequest(content="Synthetic request"),
        )


@pytest.mark.asyncio
async def test_local_model_capability_test_never_executes_tools() -> None:
    class CapabilityAdapter:
        tool_executions = 0

        async def stream_local(self, _provider_id, _model_id, _prompt, _cancel_event):
            yield "READY"

        async def complete_local(self, _provider_id, _model_id, prompt):
            if "Return only JSON" in prompt:
                return '{"status":"ok","count":2}'
            return "READY"

    model = ModelRecord(
        id="ollama/capability-fixture",
        provider_id="ollama",
        model_id="capability-fixture",
        display_name="Capability fixture",
        available=True,
        local=True,
        remote=False,
        free_status="local",
        context_window=None,
        supports_tools=None,
        supports_vision=None,
        supports_reasoning=None,
        supports_streaming=None,
        metadata_source="runtime fixture",
        last_discovered_at=datetime.now(UTC),
        runtime_id="ollama",
    )
    adapter = CapabilityAdapter()
    result = await _test_local_model_capabilities(
        adapter,  # type: ignore[arg-type]
        model,
    )
    assert result == {
        "streaming": "supported",
        "structured_output": "supported",
        "tools": "unknown",
    }
    assert adapter.tool_executions == 0


def test_hardware_profile_has_no_serial_fields() -> None:
    profile = collect_hardware_profile()
    values = profile.model_dump(mode="json")
    assert profile.os_name
    assert len(profile.profile_hash) == 64
    assert not {"serial", "serial_number", "uuid"}.intersection(values)


def test_runtime_discovery_has_only_known_defaults_and_explicit_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_LLAMA_CPP_ENDPOINT", "")
    monkeypatch.setattr(settings, "AI_VLLM_ENDPOINT", "")
    monkeypatch.setattr(settings, "AI_OPENAI_COMPATIBLE_LOCAL_ENDPOINT", "")
    definitions = configured_runtime_definitions()
    assert [item.provider_id for item in definitions] == [
        "ollama",
        "lmstudio",
        "llamacpp",
        "vllm",
        "openai_compatible_local",
    ]
    assert definitions[0].endpoint == "http://127.0.0.1:11434"
    assert definitions[1].endpoint == "http://127.0.0.1:1234"
    assert definitions[2].endpoint is None
    assert definitions[3].endpoint is None
    assert definitions[4].endpoint is None


def test_runtime_reported_metadata_is_not_inferred_from_model_name() -> None:
    now = datetime.now(UTC)
    definition = RuntimeDefinition(
        provider_id="ollama",
        name="Ollama",
        endpoint="http://127.0.0.1:11434",
        kind="ollama",
        configured=True,
    )
    models = _normalize_models(
        definition,
        [{"name": "example-70b-q4", "details": {}}],
        now,
    )
    assert len(models) == 1
    assert models[0].size_bytes is None
    assert models[0].parameter_count is None
    assert models[0].quantization is None
    assert models[0].capabilities["tools"] == "unknown"

    reported = _normalize_models(
        definition,
        [
            {
                "name": "fixture",
                "size": 5_000_000_000,
                "details": {
                    "family": "llama",
                    "parameter_size": "7B",
                    "quantization_level": "Q4_K_M",
                },
            }
        ],
        now,
    )[0]
    assert reported.size_bytes == 5_000_000_000
    assert reported.parameter_count == 7_000_000_000
    assert reported.quantization == "Q4_K_M"
    assert reported.architecture == "llama"


@pytest.mark.parametrize(
    ("size", "ram", "vram", "expected"),
    [
        (None, 16 * 1024**3, 12 * 1024**3, "unknown"),
        (5 * 1024**3, 16 * 1024**3, 12 * 1024**3, "excellent_fit"),
        (9 * 1024**3, 16 * 1024**3, 12 * 1024**3, "marginal"),
        (6 * 1024**3, 20 * 1024**3, None, "cpu_fallback"),
        (12 * 1024**3, 8 * 1024**3, 8 * 1024**3, "insufficient_memory"),
    ],
)
def test_hardware_fit_is_deterministic_and_conservative(
    size: int | None, ram: int | None, vram: int | None, expected: str
) -> None:
    fit, _reason, estimate = evaluate_model_fit(
        size_bytes=size,
        system_memory_available_bytes=ram,
        gpu_memory_bytes=vram,
    )
    assert fit == expected
    assert estimate == (None if size is None else int(size * 1.25))


class SyntheticBenchmarkAdapter:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.tool_executions = 0

    async def stream_local(
        self,
        _provider_id: str,
        _model_id: str,
        prompt: str,
        _cancel_event: asyncio.Event,
    ) -> AsyncIterator[str]:
        self.prompts.append(prompt)
        if "Reply with READY" in prompt or "Reply with READY only" in prompt:
            value = "READY"
        elif "Return only JSON matching" in prompt:
            value = '{"status":"ok","count":2}'
        elif "Synthetic evidence contains exactly two facts" in prompt:
            value = '{"facts":["service stopped","CPU 12%"]}'
        elif "Synthetic evidence: service state" in prompt:
            value = (
                '{"facts":["service stopped","CPU 12%"],"hypotheses":[],'
                '"recommendations":[],"citations":["synthetic:service-1"]}'
            )
        elif "synthetic tool registry" in prompt:
            value = '{"tool":"read_host_status","arguments":{}}'
        elif "Synthetic scenario" in prompt:
            value = '{"recommendation":"review","executed":false}'
        elif "Responde en español" in prompt:
            value = (
                "El servicio requiere revisión humana; no se ejecutó ninguna acción."
            )
        elif "In English" in prompt:
            value = (
                "The service is stopped; human review is needed; "
                "no action was executed."
            )
        elif "Synthetic Knowledge" in prompt:
            value = "The window is 30 days [synthetic:kb-1]."
        else:
            value = "No shell or tool was run."
        yield value


@pytest.mark.asyncio
async def test_benchmark_uses_synthetic_prompts_scores_without_tool_execution() -> None:
    adapter = SyntheticBenchmarkAdapter()

    async def connected() -> bool:
        return False

    result = await run_local_benchmark(
        adapter,  # type: ignore[arg-type]
        provider_id="ollama",
        model_id="synthetic-model",
        include_warmup=True,
        is_disconnected=connected,
    )
    assert result["status"] == "completed"
    scores = result["metrics"]["scores"]
    assert scores["basic_chat"] == 100.0
    assert scores["structured_output"] == 100.0
    assert scores["evidence_grounding"] == 100.0
    assert scores["citation_adherence"] == 100.0
    assert scores["tool_format"] == 100.0
    assert scores["action_safety"] == 100.0
    assert scores["spanish"] == 100.0
    assert scores["english"] == 100.0
    assert scores["knowledge"] == 100.0
    assert scores["prompt_injection"] == 100.0
    assert result["metrics"]["generated_tokens"] is not None
    assert adapter.tool_executions == 0
    assert adapter.prompts == [
        "Reply with READY only.",
        *_synthetic_cases().values(),
    ]


def test_local_provider_metadata_does_not_mark_unsupported_capabilities_as_tested() -> (
    None
):
    model = ModelRecord(
        id="llamacpp/fixture",
        provider_id="llamacpp",
        model_id="fixture",
        display_name="Fixture",
        available=True,
        local=True,
        remote=False,
        free_status="local",
        context_window=None,
        supports_tools=None,
        supports_vision=None,
        supports_reasoning=None,
        supports_streaming=None,
        metadata_source="Runtime-reported inventory",
        last_discovered_at=datetime.now(UTC),
    )
    assert model.supports_tools is None
    assert model.supports_streaming is None
    assert model.metadata_source == "Runtime-reported inventory"
