from __future__ import annotations

import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recon_entity import ReconEntity
from app.models.threat_finding import ThreatFinding
from app.models.user import User
from app.schemas.recon import EntityType, JsonProperties, TargetType
from app.schemas.threat_intel import (
    ProviderResult,
    RiskLevel,
    ThreatFindingResponse,
    ThreatIntelRequest,
    ThreatIntelResponse,
    ThreatIntelStatus,
)
from app.services.investigation import get_investigation
from app.services.target import TargetValidationError, validate_target_value
from app.services.threat_intel.abuseipdb_adapter import check_abuseipdb_ip
from app.services.threat_intel.scoring import risk_level_from_score
from app.services.threat_intel.virustotal_adapter import check_virustotal_reputation

ThreatTargetType = Literal["domain", "ip", "url"]


async def run_threat_intel_for_request(
    db: AsyncSession,
    user: User,
    body: ThreatIntelRequest,
    *,
    target_type: ThreatTargetType,
) -> ThreatIntelResponse:
    await get_investigation(db, user, body.investigation_id)
    target_value = _validate_target(target_type, body.target)
    entity = await _upsert_recon_entity(
        db,
        investigation_id=body.investigation_id,
        target_type=target_type,
        target_value=target_value,
    )
    provider_results = await _collect_provider_results(target_type, target_value)
    findings = await _persist_findings(
        db,
        investigation_id=body.investigation_id,
        entity_id=entity.id,
        target_type=target_type,
        target_value=target_value,
        provider_results=provider_results,
    )
    overall_score = max(
        (result.risk_score for result in provider_results),
        default=0,
    )
    return ThreatIntelResponse(
        investigation_id=body.investigation_id,
        entity_id=entity.id,
        target_type=target_type,
        target_value=target_value,
        status=_status_from_provider_results(provider_results),
        overall_risk_score=overall_score,
        risk_level=_risk_level(provider_results, overall_score),
        provider_results=provider_results,
        findings=[
            ThreatFindingResponse.model_validate(finding) for finding in findings
        ],
    )


async def _collect_provider_results(
    target_type: ThreatTargetType,
    target_value: str,
) -> list[ProviderResult]:
    results: list[ProviderResult] = []
    if target_type == "ip":
        results.append(
            await _provider_step(
                "abuseipdb",
                check_abuseipdb_ip(target_value),
            )
        )
    results.append(
        await _provider_step(
            "virustotal",
            check_virustotal_reputation(target_type, target_value),
        )
    )
    return results


async def _provider_step(
    provider: Literal["abuseipdb", "virustotal"],
    awaitable: Awaitable[ProviderResult],
) -> ProviderResult:
    try:
        return await awaitable
    except Exception as exc:
        return ProviderResult(
            provider=provider,
            status="failed",
            risk_score=0,
            confidence="low",
            verdict="unknown",
            error_message=exc.__class__.__name__,
        )


async def _persist_findings(
    db: AsyncSession,
    *,
    investigation_id: uuid.UUID,
    entity_id: uuid.UUID,
    target_type: TargetType,
    target_value: str,
    provider_results: list[ProviderResult],
) -> list[ThreatFinding]:
    findings: list[ThreatFinding] = []
    for result in provider_results:
        finding = ThreatFinding(
            investigation_id=investigation_id,
            recon_entity_id=entity_id,
            target_type=target_type,
            target_value=target_value,
            provider=result.provider,
            status=result.status,
            risk_score=result.risk_score,
            confidence=result.confidence,
            verdict=result.verdict,
            signals=result.signals,
            normalized_data=result.normalized,
            raw_data=result.raw_data,
            error_message=result.error_message,
        )
        db.add(finding)
        findings.append(finding)
    await db.flush()
    for finding in findings:
        await db.refresh(finding)
    return findings


async def _upsert_recon_entity(
    db: AsyncSession,
    *,
    investigation_id: uuid.UUID,
    target_type: ThreatTargetType,
    target_value: str,
) -> ReconEntity:
    entity_type = _entity_type_for_target(target_type)
    result = await db.execute(
        select(ReconEntity).where(
            ReconEntity.investigation_id == investigation_id,
            ReconEntity.entity_type == entity_type,
            ReconEntity.value == target_value,
        )
    )
    existing = result.scalar_one_or_none()
    properties: JsonProperties = {"threat_intel": True}
    if existing is not None:
        existing.properties = {**existing.properties, **properties}
        existing.source = existing.source or "threat-intel"
        existing.last_seen = datetime.now(UTC)
        db.add(existing)
        await db.flush()
        return existing

    entity = ReconEntity(
        investigation_id=investigation_id,
        entity_type=entity_type,
        value=target_value,
        display_name=target_value,
        properties=properties,
        source="threat-intel",
    )
    db.add(entity)
    await db.flush()
    return entity


def _validate_target(target_type: ThreatTargetType, value: str) -> str:
    try:
        return validate_target_value(target_type, value)
    except TargetValidationError:
        raise


def _entity_type_for_target(target_type: ThreatTargetType) -> EntityType:
    if target_type == "ip":
        return "IPAddress"
    if target_type == "domain":
        return "Domain"
    return "Service"


def _status_from_provider_results(
    provider_results: list[ProviderResult],
) -> ThreatIntelStatus:
    if not provider_results:
        return "failed"
    completed = sum(result.status == "completed" for result in provider_results)
    unavailable = sum(
        result.status == "provider_unavailable" for result in provider_results
    )
    skipped = sum(result.status == "skipped" for result in provider_results)
    if completed == len(provider_results):
        return "completed"
    if unavailable == len(provider_results):
        return "provider_unavailable"
    if skipped == len(provider_results):
        return "skipped"
    if completed:
        return "partial"
    return "failed"


def _risk_level(
    provider_results: list[ProviderResult],
    score: int,
) -> RiskLevel:
    if provider_results and all(
        result.status in ("provider_unavailable", "skipped")
        for result in provider_results
    ):
        return "unknown"
    return risk_level_from_score(score)
