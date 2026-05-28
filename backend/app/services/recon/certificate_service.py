from __future__ import annotations

from typing import Any

import httpx

from app.schemas.recon import CertificateRecord, CertificateResult, ReconError

_CRT_SH_BASE_URL = "https://crt.sh"
_TIMEOUT_SECONDS = 10.0


async def collect_certificate_intelligence(
    domain: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> CertificateResult:
    normalized = domain.strip().lower().rstrip(".")
    owned_client = client is None
    errors: list[ReconError] = []

    if client is None:
        client = httpx.AsyncClient(base_url=_CRT_SH_BASE_URL, timeout=_TIMEOUT_SECONDS)

    try:
        response = await client.get(
            "/",
            params={"q": f"%.{normalized}", "output": "json"},
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        payload = []
        errors.append(ReconError(source="crt.sh", message=_safe_error(exc)))
    finally:
        if owned_client:
            await client.aclose()

    rows = payload if isinstance(payload, list) else []
    certificates: list[CertificateRecord] = []
    subdomains: set[str] = set()

    for row in rows:
        if not isinstance(row, dict):
            continue
        names = _extract_names(row.get("name_value"), normalized)
        subdomains.update(name for name in names if name != normalized)
        certificate_id = row.get("id") or row.get("min_cert_id") or row.get("cert_id")
        if certificate_id is None:
            continue
        certificates.append(
            CertificateRecord(
                certificate_id=str(certificate_id),
                san_names=names,
                issuer=_string_or_none(row.get("issuer_name")),
                expires_at=_string_or_none(row.get("not_after")),
            )
        )

    return CertificateResult(
        domain=normalized,
        certificates=certificates,
        subdomains=sorted(subdomains),
        errors=errors,
    )


def _extract_names(raw: Any, base_domain: str) -> list[str]:
    if not isinstance(raw, str):
        return []
    names: set[str] = set()
    for item in raw.replace(",", "\n").splitlines():
        clean = item.strip().lower().rstrip(".")
        if clean.startswith("*."):
            clean = clean[2:]
        if clean == base_domain or clean.endswith(f".{base_domain}"):
            names.add(clean)
    return sorted(names)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "crt.sh request timed out"
    return exc.__class__.__name__
