from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import settings
from app.schemas.analysis import AnalysisProviderStatus

_ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_DEFAULT_TIMEOUT_SECONDS = 30.0
_MAX_RETRIES = 2


@dataclass(frozen=True)
class ProviderCompletion:
    status: AnalysisProviderStatus
    content: str = ""
    provider: str = "anthropic"
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None


class LLMProvider(Protocol):
    async def complete(self, prompt: str) -> ProviderCompletion: ...


class AnthropicClaudeProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.ANTHROPIC_API_KEY
        self._model = model or settings.ANTHROPIC_MODEL
        self._timeout_seconds = timeout_seconds

    async def complete(self, prompt: str) -> ProviderCompletion:
        if not self._api_key:
            return ProviderCompletion(
                status="provider_unavailable",
                model=self._model,
                error="ANTHROPIC_API_KEY is not configured.",
            )

        payload = {
            "model": self._model,
            "max_tokens": 1800,
            "temperature": 0.1,
            "system": "You are a defensive cybersecurity analyst. Return JSON only.",
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
            "x-api-key": self._api_key,
        }
        last_error: str | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(
                        _ANTHROPIC_MESSAGES_URL,
                        headers=headers,
                        json=payload,
                    )
                if response.status_code == 429:
                    last_error = "Anthropic provider rate limited the request."
                    await asyncio.sleep(0.25 * (attempt + 1))
                    continue
                if response.status_code >= 500:
                    last_error = f"Anthropic provider returned {response.status_code}."
                    await asyncio.sleep(0.25 * (attempt + 1))
                    continue
                if response.status_code >= 400:
                    return ProviderCompletion(
                        status="provider_failed",
                        model=self._model,
                        error=f"Anthropic provider returned {response.status_code}.",
                    )
                return _completion_from_payload(response.json(), self._model)
            except httpx.TimeoutException:
                return ProviderCompletion(
                    status="provider_timeout",
                    model=self._model,
                    error="Anthropic provider request timed out.",
                )
            except Exception as exc:
                last_error = _safe_error(exc)
                await asyncio.sleep(0.25 * (attempt + 1))

        return ProviderCompletion(
            status="provider_failed",
            model=self._model,
            error=last_error or "Anthropic provider failed.",
        )


def _completion_from_payload(payload: dict[str, Any], model: str) -> ProviderCompletion:
    content_blocks = payload.get("content")
    text_parts: list[str] = []
    if isinstance(content_blocks, list):
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
    usage = payload.get("usage")
    usage_data = usage if isinstance(usage, dict) else {}
    if not text_parts:
        return ProviderCompletion(
            status="provider_failed",
            model=model,
            error="Anthropic response did not include text content.",
        )
    return ProviderCompletion(
        status="completed",
        content="\n".join(text_parts),
        model=str(payload.get("model") or model),
        input_tokens=_int_or_none(usage_data.get("input_tokens")),
        output_tokens=_int_or_none(usage_data.get("output_tokens")),
    )


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _safe_error(exc: Exception) -> str:
    message = str(exc).strip()
    return message[:300] if message else exc.__class__.__name__
