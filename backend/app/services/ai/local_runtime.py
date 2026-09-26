from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.config import settings
from app.schemas.ai_gateway import AiLocalRuntime, CapabilityState, RuntimeState

if TYPE_CHECKING:
    from app.services.ai.opencode_adapter import ModelRecord

_TIMEOUT = httpx.Timeout(1.8, connect=0.5, read=1.2)
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,239}$")
_CACHE_TTL_SECONDS = 15.0
_CACHE_LOCK = asyncio.Lock()
_AUTH_REQUIRED_MESSAGE = (
    "Runtime requires authentication; credentials are not collected or forwarded."
)


@dataclass(frozen=True)
class RuntimeDefinition:
    provider_id: str
    name: str
    endpoint: str | None
    kind: str
    configured: bool


@dataclass(frozen=True)
class RuntimeDiscovery:
    runtime: AiLocalRuntime
    provider: dict[str, Any]
    models: tuple[ModelRecord, ...]


_cached_at = 0.0
_cached_discovery: tuple[RuntimeDiscovery, ...] | None = None


def configured_runtime_definitions() -> tuple[RuntimeDefinition, ...]:
    return (
        RuntimeDefinition("ollama", "Ollama", "http://127.0.0.1:11434", "ollama", True),
        RuntimeDefinition(
            "lmstudio", "LM Studio", "http://127.0.0.1:1234", "openai", True
        ),
        RuntimeDefinition(
            "llamacpp",
            "llama.cpp",
            settings.AI_LLAMA_CPP_ENDPOINT or None,
            "openai",
            bool(settings.AI_LLAMA_CPP_ENDPOINT),
        ),
        RuntimeDefinition(
            "vllm",
            "vLLM",
            settings.AI_VLLM_ENDPOINT or None,
            "openai",
            bool(settings.AI_VLLM_ENDPOINT),
        ),
        RuntimeDefinition(
            "openai_compatible_local",
            "OpenAI-compatible local runtime",
            settings.AI_OPENAI_COMPATIBLE_LOCAL_ENDPOINT or None,
            "openai",
            bool(settings.AI_OPENAI_COMPATIBLE_LOCAL_ENDPOINT),
        ),
    )


async def discover_local_runtimes(
    *, refresh: bool = False
) -> tuple[RuntimeDiscovery, ...]:
    global _cached_at, _cached_discovery
    now = time.monotonic()
    if (
        not refresh
        and _cached_discovery is not None
        and now - _cached_at < _CACHE_TTL_SECONDS
    ):
        return _cached_discovery
    async with _CACHE_LOCK:
        now = time.monotonic()
        if (
            not refresh
            and _cached_discovery is not None
            and now - _cached_at < _CACHE_TTL_SECONDS
        ):
            return _cached_discovery
        definitions = configured_runtime_definitions()
        results = await asyncio.gather(
            *(_probe(definition) for definition in definitions),
            return_exceptions=True,
        )
        discovered: list[RuntimeDiscovery] = []
        for definition, result in zip(definitions, results, strict=True):
            if isinstance(result, RuntimeDiscovery):
                discovered.append(result)
            else:
                discovered.append(
                    _unavailable(definition, "Runtime probe failed safely.")
                )
        _cached_at = time.monotonic()
        _cached_discovery = tuple(discovered)
        return _cached_discovery


async def discover_local_catalog(
    *, refresh: bool = False
) -> tuple[list[dict[str, Any]], list[ModelRecord]]:
    discoveries = await discover_local_runtimes(refresh=refresh)
    providers = [
        item.provider
        for item in discoveries
        if item.runtime.status in {"available", "no_models"}
    ]
    models = [model for item in discoveries for model in item.models]
    return providers, models


async def _probe(definition: RuntimeDefinition) -> RuntimeDiscovery:
    now = datetime.now(UTC)
    if definition.endpoint is None:
        return _unavailable(
            definition, "No operator-configured loopback endpoint.", state="unknown"
        )
    try:
        endpoint = safe_loopback_endpoint(definition.endpoint)
    except ValueError:
        network_endpoint = _is_network_endpoint(definition.endpoint)
        return _unavailable(
            definition,
            (
                "Configured endpoint is network-addressed and blocked; "
                "use a loopback address."
                if network_endpoint
                else "Configured endpoint is blocked; use an HTTP loopback address."
            ),
            state="incompatible",
            endpoint_classification="network" if network_endpoint else "unknown",
        )

    headers = {"Accept": "application/json"}
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, follow_redirects=False, trust_env=False
        ) as client:
            if definition.kind == "ollama":
                response = await client.get(f"{endpoint}/api/tags", headers=headers)
                if response.status_code == 404:
                    return _unavailable(
                        definition,
                        "Ollama API endpoint did not match.",
                        state="incompatible",
                        endpoint=endpoint,
                    )
                response.raise_for_status()
                payload = response.json()
                entries = payload.get("models", []) if isinstance(payload, dict) else []
                version = await _ollama_version(client, endpoint)
            else:
                models_url = _join_endpoint(endpoint, "v1/models")
                response = await client.get(models_url, headers=headers)
                if response.status_code == 401 or response.status_code == 403:
                    return _unavailable(
                        definition,
                        _AUTH_REQUIRED_MESSAGE,
                        state="authentication_required",
                        endpoint=endpoint,
                    )
                response.raise_for_status()
                payload = response.json()
                entries = payload.get("data", []) if isinstance(payload, dict) else []
                version = _safe_version_header(
                    response.headers.get("x-runtime-version")
                )
                if definition.provider_id in {"llamacpp", "vllm"}:
                    version = version or await _optional_version(
                        client, endpoint, definition.provider_id
                    )
    except httpx.TimeoutException:
        return _unavailable(definition, "Runtime probe timed out.", endpoint=endpoint)
    except httpx.ConnectError:
        return _unavailable(
            definition,
            "Runtime is not responding on the configured loopback endpoint.",
            endpoint=endpoint,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            return _unavailable(
                definition,
                _AUTH_REQUIRED_MESSAGE,
                state="authentication_required",
                endpoint=endpoint,
            )
        return _unavailable(
            definition,
            "Runtime returned an unsuccessful health response.",
            state="degraded",
            endpoint=endpoint,
        )
    except (httpx.HTTPError, ValueError):
        return _unavailable(
            definition,
            "Runtime response was unavailable or not valid JSON.",
            state="incompatible",
            endpoint=endpoint,
        )

    normalized = _normalize_models(definition, entries, now)
    status: RuntimeState = "available" if normalized else "no_models"
    message = (
        "Loopback runtime is responding."
        if normalized
        else "Runtime is responding but reports no installed models."
    )
    runtime = AiLocalRuntime(
        id=definition.provider_id,
        provider_id=definition.provider_id,
        name=definition.name,
        status=status,
        endpoint=endpoint,
        version=version,
        model_count=len(normalized),
        loopback_only=True,
        capabilities={
            "chat": "supported",
            "streaming": "unknown",
            "structured_output": "unknown",
            "tools": "unknown",
        },
        message=message,
    )
    provider = {
        "id": definition.provider_id,
        "name": definition.name,
        "category": definition.provider_id,
        "connected": bool(normalized),
        "local": True,
        "remote": False,
        "status": status,
    }
    return RuntimeDiscovery(
        runtime=runtime, provider=provider, models=tuple(normalized)
    )


def _normalize_models(
    definition: RuntimeDefinition, entries: Any, discovered_at: datetime
) -> list[ModelRecord]:
    if not isinstance(entries, list):
        return []
    models: list[ModelRecord] = []
    from app.services.ai.opencode_adapter import ModelRecord

    for entry in entries[:128]:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("name") or entry.get("model") or entry.get("id")
        if not isinstance(model_id, str) or not _MODEL_ID.fullmatch(model_id):
            continue
        raw_details = entry.get("details")
        details: dict[str, Any] = {}
        if isinstance(raw_details, dict):
            details = raw_details
        size_value = entry.get("size")
        size_bytes = (
            size_value
            if isinstance(size_value, int)
            and not isinstance(size_value, bool)
            and size_value > 0
            else None
        )
        family = details.get("family")
        architecture = family[:80] if isinstance(family, str) and family else None
        parameter_size = details.get("parameter_size")
        parameter_count = _reported_parameter_count(parameter_size)
        quantization_value = details.get("quantization_level")
        quantization = (
            quantization_value[:32]
            if isinstance(quantization_value, str) and quantization_value
            else None
        )
        model_context = entry.get("context_length")
        context_window = (
            model_context
            if isinstance(model_context, int)
            and not isinstance(model_context, bool)
            and model_context > 0
            else None
        )
        capabilities: dict[str, CapabilityState] = {
            "chat": "supported",
            "streaming": "unknown",
            "reasoning": "unknown",
            "tools": "unknown",
            "structured_output": "unknown",
            "vision": "unknown",
            "embeddings": "unknown",
            "system_prompt": "unknown",
            "long_context": "unknown",
        }
        metadata = (
            "Runtime-reported inventory"
            if definition.provider_id != "ollama"
            else "Ollama-reported model metadata"
        )
        models.append(
            ModelRecord(
                id=f"{definition.provider_id}/{model_id}",
                provider_id=definition.provider_id,
                model_id=model_id,
                display_name=_safe_label(
                    entry.get("name") or entry.get("id") or model_id
                ),
                available=True,
                local=True,
                remote=False,
                free_status="local",
                context_window=context_window,
                supports_tools=None,
                supports_vision=None,
                supports_reasoning=None,
                supports_streaming=None,
                metadata_source=metadata,
                last_discovered_at=discovered_at,
                runtime_id=definition.provider_id,
                size_bytes=size_bytes,
                parameter_count=parameter_count,
                quantization=quantization,
                architecture=architecture,
                capabilities=cast(dict[str, str], capabilities),
            )
        )
    return models


def safe_loopback_endpoint(value: str) -> str:
    """Validate a configured base URL and pin it to a loopback IP address."""
    normalized = safe_loopback_url(value)
    parsed = urlsplit(normalized)
    if parsed.path not in {"", "/", "/v1", "/v1/"}:
        raise ValueError("Only an optional /v1 endpoint path is supported.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def safe_loopback_url(value: str) -> str:
    """Validate an HTTP request URL and pin localhost to its resolved loopback IP."""
    if not isinstance(value, str) or len(value) > 300:
        raise ValueError("Endpoint is invalid.")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only HTTP(S) loopback endpoints are supported.")
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Credentials and query strings are not accepted in endpoints.")
    if "\\" in parsed.path or any(part == ".." for part in parsed.path.split("/")):
        raise ValueError("Endpoint path is invalid.")
    if any(ord(char) < 32 for char in parsed.path):
        raise ValueError("Endpoint path is invalid.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Endpoint port is invalid.") from exc
    host = parsed.hostname.casefold().rstrip(".")
    if host == "localhost":
        try:
            resolved = {
                ipaddress.ip_address(str(item[4][0]).split("%", 1)[0])
                for item in socket.getaddrinfo(
                    host,
                    port or (443 if parsed.scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            }
        except (OSError, ValueError) as exc:
            raise ValueError("localhost could not be resolved safely.") from exc
        if not resolved or any(not address.is_loopback for address in resolved):
            raise ValueError("localhost resolved outside loopback.")
        # Pin the URL to the resolved loopback address to avoid a second DNS lookup.
        address = next(iter(sorted(resolved, key=lambda item: item.version)))
        host = address.compressed
    else:
        try:
            address = ipaddress.ip_address(host.split("%", 1)[0])
        except ValueError as exc:
            raise ValueError(
                "Only numeric loopback or localhost hosts are supported."
            ) from exc
        if not address.is_loopback:
            raise ValueError("Endpoint is not loopback.")
        host = address.compressed
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc += f":{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def local_runtime_endpoint(provider_id: str) -> str:
    definition = next(
        (
            item
            for item in configured_runtime_definitions()
            if item.provider_id == provider_id
        ),
        None,
    )
    if definition is None or definition.endpoint is None:
        raise RuntimeError("The local runtime has no operator-configured endpoint.")
    endpoint = safe_loopback_endpoint(definition.endpoint)
    parsed = urlsplit(endpoint)
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _unavailable(
    definition: RuntimeDefinition,
    message: str,
    *,
    state: str = "unavailable",
    endpoint: str | None = None,
    endpoint_classification: str = "loopback",
) -> RuntimeDiscovery:
    safe_display = endpoint or (
        "loopback default" if definition.endpoint else "operator-configured endpoint"
    )
    runtime = AiLocalRuntime(
        id=definition.provider_id,
        provider_id=definition.provider_id,
        name=definition.name,
        status=state,  # type: ignore[arg-type]
        endpoint=safe_display,
        version=None,
        model_count=0,
        loopback_only=endpoint_classification != "network",
        endpoint_classification=endpoint_classification,  # type: ignore[arg-type]
        capabilities={
            "chat": "unknown",
            "streaming": "unknown",
            "structured_output": "unknown",
            "tools": "unknown",
        },
        message=message,
    )
    provider = {
        "id": definition.provider_id,
        "name": definition.name,
        "category": definition.provider_id,
        "connected": False,
        "local": endpoint_classification != "network",
        "remote": endpoint_classification == "network",
        "status": state,
    }
    return RuntimeDiscovery(runtime=runtime, provider=provider, models=())


def _is_network_endpoint(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if not host:
            return False
        if host.casefold().rstrip(".") == "localhost":
            resolved = socket.getaddrinfo(
                host,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
            return any(
                not ipaddress.ip_address(str(item[4][0]).split("%", 1)[0]).is_loopback
                for item in resolved
            )
        try:
            return not ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
        except ValueError:
            return True
    except (OSError, ValueError):
        return True


async def _ollama_version(client: httpx.AsyncClient, endpoint: str) -> str | None:
    try:
        response = await client.get(f"{endpoint}/api/version")
        if response.is_success:
            value = response.json().get("version")
            return _safe_version_header(value)
    except (httpx.HTTPError, ValueError, AttributeError):
        return None
    return None


async def _optional_version(
    client: httpx.AsyncClient, endpoint: str, provider_id: str
) -> str | None:
    path = "version" if provider_id == "vllm" else "health"
    try:
        response = await client.get(_join_endpoint(endpoint, path))
        if response.is_success:
            return _safe_version_header(response.headers.get("x-runtime-version"))
    except httpx.HTTPError:
        return None
    return None


def _join_endpoint(endpoint: str, path: str) -> str:
    if path.startswith("v1/"):
        suffix = path.removeprefix("v1/")
        base = endpoint if endpoint.endswith("/v1") else f"{endpoint}/v1"
        return f"{base}/{suffix}"
    base = endpoint.removesuffix("/v1")
    return f"{base}/{path}"


def _reported_parameter_count(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMB])\s*", value, re.IGNORECASE)
    if not match:
        return None
    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[
        match.group(2).upper()
    ]
    return int(float(match.group(1)) * multiplier)


def _safe_label(value: Any) -> str:
    if not isinstance(value, str):
        return "Local model"
    clean = " ".join(value.split())
    return clean[:200] or "Local model"


def _safe_version_header(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    clean = "".join(char for char in value if char.isalnum() or char in ".-+_ ")[
        :80
    ].strip()
    return clean or None
