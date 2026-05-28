from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urlparse

import httpx

from app.schemas.recon import (
    CookieSummary,
    HTTPResult,
    ReconError,
    SecurityHeaders,
    TLSCertificateSummary,
)

_TIMEOUT_SECONDS = 8.0
_MAX_REDIRECTS = 5


async def inspect_http_metadata(
    target: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> HTTPResult:
    url = _normalize_url(target)
    owned_client = client is None
    errors: list[ReconError] = []
    redirect_chain: list[str] = []

    if client is None:
        client = httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, follow_redirects=False)

    try:
        response = await _safe_request(client, url)
        redirects = 0
        while response.is_redirect and redirects < _MAX_REDIRECTS:
            location = response.headers.get("location")
            if not location:
                break
            next_url = str(response.url.join(location))
            redirect_chain.append(next_url)
            response = await _safe_request(client, next_url)
            redirects += 1
    except Exception as exc:
        response = None
        errors.append(ReconError(source="http", message=_safe_error(exc)))
    finally:
        if owned_client:
            await client.aclose()

    if response is None:
        return HTTPResult(url=url, errors=errors)

    headers = {key.lower(): value for key, value in response.headers.items()}
    tls_version, certificate = _tls_summary(response)
    return HTTPResult(
        url=url,
        final_url=str(response.url),
        status_code=response.status_code,
        headers=headers,
        security_headers=SecurityHeaders(
            hsts=headers.get("strict-transport-security"),
            csp=headers.get("content-security-policy"),
            x_frame_options=headers.get("x-frame-options"),
            x_content_type_options=headers.get("x-content-type-options"),
            referrer_policy=headers.get("referrer-policy"),
        ),
        cookies=_cookie_summaries(response),
        server=headers.get("server"),
        content_type=headers.get("content-type"),
        redirect_chain=redirect_chain,
        tls_version=tls_version,
        certificate=certificate,
        errors=errors,
    )


async def _safe_request(client: httpx.AsyncClient, url: str) -> httpx.Response:
    response = await client.request("HEAD", url)
    if response.status_code in (405, 501):
        response = await client.request("GET", url)
    return response


def _normalize_url(target: str) -> str:
    clean = target.strip()
    parsed = urlparse(clean)
    if parsed.scheme in ("http", "https"):
        return clean
    return f"https://{clean}"


def _cookie_summaries(response: httpx.Response) -> list[CookieSummary]:
    summaries: list[CookieSummary] = []
    for raw_cookie in response.headers.get_list("set-cookie"):
        cookie = SimpleCookie()
        cookie.load(raw_cookie)
        for name, morsel in cookie.items():
            summaries.append(
                CookieSummary(
                    name=name,
                    secure=bool(morsel["secure"]),
                    http_only=bool(morsel["httponly"]),
                    same_site=morsel["samesite"] or None,
                )
            )
    return summaries


def _tls_summary(
    response: httpx.Response,
) -> tuple[str | None, TLSCertificateSummary | None]:
    stream = response.extensions.get("network_stream")
    ssl_object = _get_extra_info(stream, "ssl_object")
    if ssl_object is None:
        return None, None

    version = _call_or_none(ssl_object, "version")
    cert = _call_or_none(ssl_object, "getpeercert")
    if not isinstance(cert, dict):
        return _string_or_none(version), None

    san_names = [
        value
        for key, value in cert.get("subjectAltName", [])
        if key == "DNS" and isinstance(value, str)
    ]
    return _string_or_none(version), TLSCertificateSummary(
        subject=_dn_tuple_to_string(cert.get("subject")),
        issuer=_dn_tuple_to_string(cert.get("issuer")),
        not_before=_string_or_none(cert.get("notBefore")),
        not_after=_string_or_none(cert.get("notAfter")),
        san_names=sorted(set(san_names)),
    )


def _get_extra_info(stream: Any, key: str) -> Any:
    getter = getattr(stream, "get_extra_info", None)
    if callable(getter):
        return getter(key)
    return None


def _call_or_none(obj: Any, method_name: str) -> Any:
    method = getattr(obj, method_name, None)
    if callable(method):
        return method()
    return None


def _dn_tuple_to_string(value: Any) -> str | None:
    if not isinstance(value, tuple):
        return None
    parts: list[str] = []
    for group in value:
        if not isinstance(group, tuple):
            continue
        for item in group:
            if isinstance(item, tuple) and len(item) == 2:
                parts.append(f"{item[0]}={item[1]}")
    return ", ".join(parts) if parts else None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "HTTP request timed out"
    return exc.__class__.__name__
