from __future__ import annotations

import ipaddress
import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.investigation_enrichment import InvestigationEnrichment
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.user import User
from app.schemas.recon import (
    CertificateResult,
    DNSRecordType,
    DNSResult,
    HTTPResult,
    IPResult,
    JsonProperties,
    RDAPResult,
    ReconError,
    ReconRequest,
    ReconResponse,
)
from app.services.investigation import get_investigation
from app.services.recon.certificate_service import collect_certificate_intelligence
from app.services.recon.dns_service import collect_dns_intelligence
from app.services.recon.http_service import inspect_http_metadata
from app.services.recon.ip_service import collect_ip_intelligence
from app.services.recon.normalization import normalize_recon_entities
from app.services.recon.rdap_service import collect_rdap_intelligence
from app.services.target import TargetValidationError, validate_target_value

TargetType = Literal["domain", "ip", "url"]


async def run_recon_for_request(
    db: AsyncSession,
    user: User,
    body: ReconRequest,
    *,
    target_type: TargetType,
) -> ReconResponse:
    await get_investigation(db, user, body.investigation_id)
    target_value = _validate_target(target_type, body.target)
    response = await run_recon_pipeline(target_type, target_value)
    response.investigation_id = body.investigation_id
    graph = normalize_recon_entities(response)
    response.entities = graph.entities
    response.relationships = graph.relationships
    await _persist_recon_result(db, user, body, response)
    return response


async def run_recon_pipeline(
    target_type: TargetType, target_value: str
) -> ReconResponse:
    errors: list[ReconError] = []
    dns: DNSResult | None = None
    rdap: RDAPResult | None = None
    certificates: CertificateResult | None = None
    ip: IPResult | None = None
    http: HTTPResult | None = None

    if target_type == "domain":
        dns = await _step("dns", collect_dns_intelligence(target_value), errors)
        rdap = await _step(
            "rdap",
            collect_rdap_intelligence(target_value, target_type="domain"),
            errors,
        )
        certificates = await _step(
            "crt.sh",
            collect_certificate_intelligence(target_value),
            errors,
        )
        first_ip = _first_dns_ip(dns)
        if first_ip:
            ip = await _step("ip-rdap", collect_ip_intelligence(first_ip), errors)
        http = await _step("http", inspect_http_metadata(target_value), errors)
    elif target_type == "ip":
        ip = await _step("ip-rdap", collect_ip_intelligence(target_value), errors)
        rdap = await _step(
            "rdap",
            collect_rdap_intelligence(target_value, target_type="ip"),
            errors,
        )
        http = await _step("http", inspect_http_metadata(target_value), errors)
    else:
        host = urlparse(target_value).hostname or target_value
        if _is_ip(host):
            ip = await _step("ip-rdap", collect_ip_intelligence(host), errors)
            rdap = await _step(
                "rdap",
                collect_rdap_intelligence(host, target_type="ip"),
                errors,
            )
        else:
            dns = await _step("dns", collect_dns_intelligence(host), errors)
            rdap = await _step(
                "rdap",
                collect_rdap_intelligence(host, target_type="domain"),
                errors,
            )
            certificates = await _step(
                "crt.sh",
                collect_certificate_intelligence(host),
                errors,
            )
        http = await _step("http", inspect_http_metadata(target_value), errors)

    errors.extend(_component_errors(dns, rdap, certificates, ip, http))
    status = _status_from_results(errors, dns, rdap, certificates, ip, http)
    return ReconResponse(
        target_type=target_type,
        target_value=target_value,
        status=status,
        dns=dns,
        rdap=rdap,
        certificates=certificates,
        ip=ip,
        http=http,
        errors=errors,
    )


async def _step[T](
    source: str,
    awaitable: Awaitable[T],
    errors: list[ReconError],
) -> T | None:
    try:
        return await awaitable
    except Exception as exc:
        errors.append(ReconError(source=source, message=exc.__class__.__name__))
        return None


def _validate_target(target_type: TargetType, value: str) -> str:
    if target_type == "domain":
        return validate_target_value("domain", value)
    if target_type == "ip":
        return validate_target_value("ip", value)
    normalized = validate_target_value("url", value)
    parsed = urlparse(normalized)
    if parsed.scheme not in ("http", "https"):
        raise TargetValidationError("URL targets must be valid http/https URLs")
    return normalized


def _first_dns_ip(dns: DNSResult | None) -> str | None:
    if dns is None:
        return None
    address_records: tuple[DNSRecordType, ...] = ("A", "AAAA")
    for record_type in address_records:
        values = dns.record_values(record_type)
        if values:
            return values[0]
    return None


def _component_errors(
    *components: DNSResult
    | RDAPResult
    | CertificateResult
    | IPResult
    | HTTPResult
    | None,
) -> list[ReconError]:
    errors: list[ReconError] = []
    for component in components:
        if component is not None:
            errors.extend(component.errors)
    return errors


def _status_from_results(
    errors: list[ReconError],
    *components: DNSResult
    | RDAPResult
    | CertificateResult
    | IPResult
    | HTTPResult
    | None,
) -> Literal["completed", "partial", "failed"]:
    successes = sum(
        component is not None and not component.errors for component in components
    )
    if successes == 0 and errors:
        return "failed"
    return "partial" if errors else "completed"


async def _persist_recon_result(
    db: AsyncSession,
    user: User,
    body: ReconRequest,
    response: ReconResponse,
) -> None:
    entity_ids: dict[tuple[str, str], uuid.UUID] = {}
    for entity in response.entities:
        persisted = await _upsert_entity(
            db,
            investigation_id=body.investigation_id,
            entity_type=entity.entity_type,
            value=entity.value,
            display_name=entity.display_name,
            properties=entity.properties,
            source=entity.source,
        )
        entity_ids[(entity.entity_type, entity.value)] = persisted.id

    for relationship in response.relationships:
        source_id = entity_ids.get(
            (relationship.source_type, relationship.source_value)
        )
        target_id = entity_ids.get(
            (relationship.target_type, relationship.target_value)
        )
        if source_id is None or target_id is None:
            continue
        await _upsert_relationship(
            db,
            investigation_id=body.investigation_id,
            source_entity_id=source_id,
            target_entity_id=target_id,
            relationship_type=relationship.relationship_type,
            properties=relationship.properties,
            source=relationship.source,
        )

    enrichment = InvestigationEnrichment(
        investigation_id=body.investigation_id,
        initiated_by=user.id,
        target_type=response.target_type,
        target_value=response.target_value,
        authorization_statement=body.authorization_statement,
        status=response.status,
        summary={
            "entity_count": len(response.entities),
            "relationship_count": len(response.relationships),
            "error_count": len(response.errors),
        },
        result=response.model_dump(mode="json"),
    )
    db.add(enrichment)
    await db.flush()
    response.enrichment_id = enrichment.id
    enrichment.result = response.model_dump(mode="json")
    db.add(enrichment)
    await db.flush()


async def _upsert_entity(
    db: AsyncSession,
    *,
    investigation_id: uuid.UUID,
    entity_type: str,
    value: str,
    display_name: str | None,
    properties: JsonProperties,
    source: str | None,
) -> ReconEntity:
    result = await db.execute(
        select(ReconEntity).where(
            ReconEntity.investigation_id == investigation_id,
            ReconEntity.entity_type == entity_type,
            ReconEntity.value == value,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.display_name = display_name or existing.display_name
        existing.properties = {**existing.properties, **properties}
        existing.source = source or existing.source
        existing.last_seen = datetime.now(UTC)
        db.add(existing)
        await db.flush()
        return existing

    entity = ReconEntity(
        investigation_id=investigation_id,
        entity_type=entity_type,
        value=value,
        display_name=display_name,
        properties=properties,
        source=source,
    )
    db.add(entity)
    await db.flush()
    return entity


async def _upsert_relationship(
    db: AsyncSession,
    *,
    investigation_id: uuid.UUID,
    source_entity_id: uuid.UUID,
    target_entity_id: uuid.UUID,
    relationship_type: str,
    properties: JsonProperties,
    source: str | None,
) -> ReconRelationship:
    result = await db.execute(
        select(ReconRelationship).where(
            ReconRelationship.investigation_id == investigation_id,
            ReconRelationship.source_entity_id == source_entity_id,
            ReconRelationship.target_entity_id == target_entity_id,
            ReconRelationship.relationship_type == relationship_type,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.properties = {**existing.properties, **properties}
        existing.source = source or existing.source
        db.add(existing)
        await db.flush()
        return existing

    relationship = ReconRelationship(
        investigation_id=investigation_id,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        relationship_type=relationship_type,
        properties=properties,
        source=source,
    )
    db.add(relationship)
    await db.flush()
    return relationship


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True
