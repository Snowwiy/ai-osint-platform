from __future__ import annotations

import json
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.analysis import (
    AnalysisFrameworkMapping,
    AnalysisRecommendation,
    AnalysisResponse,
    CitedAnalysisText,
    IocAnalysisRequest,
    InvestigationAnalysisRequest,
    ThreatContextAnalysisRequest,
)
from app.schemas.finding import FindingSeverity
from app.services.ai.evidence_builder import (
    EvidenceBundle,
    EvidenceItem,
    build_investigation_evidence,
    build_ioc_evidence,
    build_threat_context_evidence,
    citations_from_items,
)
from app.services.ai.framework_mapper import map_frameworks
from app.services.ai.knowledge_retriever import retrieve_knowledge_context
from app.services.ai.llm_provider import (
    AnthropicClaudeProvider,
    LLMProvider,
    ProviderCompletion,
)
from app.services.ai.prompt_builder import build_analysis_prompt
from app.services.investigation import get_investigation

_SEVERITIES: tuple[FindingSeverity, ...] = (
    "info",
    "low",
    "medium",
    "high",
    "critical",
)
_SEVERITY_RANK: dict[FindingSeverity, int] = {
    severity: index for index, severity in enumerate(_SEVERITIES)
}


def get_llm_provider() -> LLMProvider:
    return AnthropicClaudeProvider()


async def analyze_investigation(
    db: AsyncSession,
    user: User,
    body: InvestigationAnalysisRequest,
    *,
    provider: LLMProvider | None = None,
) -> AnalysisResponse:
    await get_investigation(db, user, body.investigation_id)
    evidence = await build_investigation_evidence(db, user, body.investigation_id)
    return await _run_analysis(
        db,
        evidence=evidence,
        mode="investigation",
        provider=provider,
    )


async def analyze_ioc(
    db: AsyncSession,
    user: User,
    body: IocAnalysisRequest,
    *,
    provider: LLMProvider | None = None,
) -> AnalysisResponse:
    await get_investigation(db, user, body.investigation_id)
    evidence = await build_ioc_evidence(
        db,
        user,
        body.investigation_id,
        ioc_type=body.ioc_type,
        value=body.value,
    )
    return await _run_analysis(
        db,
        evidence=evidence,
        mode="ioc",
        provider=provider,
        target_type=body.ioc_type,
        target_value=body.value,
    )


async def analyze_threat_context(
    db: AsyncSession,
    user: User,
    body: ThreatContextAnalysisRequest,
    *,
    provider: LLMProvider | None = None,
) -> AnalysisResponse:
    await get_investigation(db, user, body.investigation_id)
    evidence = await build_threat_context_evidence(
        db,
        user,
        body.investigation_id,
        finding_ids=body.finding_ids,
    )
    return await _run_analysis(
        db,
        evidence=evidence,
        mode="threat_context",
        provider=provider,
    )


async def _run_analysis(
    db: AsyncSession,
    *,
    evidence: EvidenceBundle,
    mode: str,
    provider: LLMProvider | None,
    target_type: str | None = None,
    target_value: str | None = None,
) -> AnalysisResponse:
    knowledge = await retrieve_knowledge_context(db, evidence, mode="hybrid")
    framework_mappings = map_frameworks(evidence.items, knowledge.items)
    all_items = [*evidence.items, *knowledge.items]
    prompt = build_analysis_prompt(
        mode=cast(Any, mode),
        evidence_items=evidence.items,
        knowledge_items=knowledge.items,
        framework_mappings=framework_mappings,
        target_type=cast(Any, target_type),
        target_value=target_value,
    )
    llm_provider = provider or get_llm_provider()
    completion = await llm_provider.complete(prompt)

    fallback = _fallback_response(
        evidence=evidence,
        knowledge_items=knowledge.items,
        framework_mappings=framework_mappings,
        mode=mode,
        completion=completion,
        target_type=target_type,
        target_value=target_value,
    )
    if completion.status != "completed":
        return fallback

    parsed = _parse_llm_content(completion.content)
    if parsed is None:
        fallback.status = "malformed_response"
        fallback.errors.append("LLM response was not valid analysis JSON.")
        return fallback

    response = _response_from_llm(
        parsed,
        evidence=evidence,
        knowledge_items=knowledge.items,
        framework_mappings=framework_mappings,
        mode=mode,
        completion=completion,
        target_type=target_type,
        target_value=target_value,
    )
    if response is None:
        fallback.status = "malformed_response"
        fallback.errors.append("LLM response did not include valid evidence citations.")
        return fallback
    response.citations = citations_from_items(all_items)
    return response


def _response_from_llm(
    payload: dict[str, Any],
    *,
    evidence: EvidenceBundle,
    knowledge_items: list[EvidenceItem],
    framework_mappings: list[AnalysisFrameworkMapping],
    mode: str,
    completion: ProviderCompletion,
    target_type: str | None,
    target_value: str | None,
) -> AnalysisResponse | None:
    all_items = [*evidence.items, *knowledge_items]
    allowed = {item.id for item in all_items}
    fallback_citation = _first_citation(all_items)
    executive = _cited_text(payload.get("executive_summary"), allowed)
    technical = _cited_text(payload.get("technical_summary"), allowed)
    if (executive is None or technical is None) and allowed:
        return None

    suspicious = _cited_text_list(payload.get("suspicious_findings"), allowed)
    indicators = _cited_text_list(payload.get("observed_indicators"), allowed)
    hypotheses = _cited_text_list(payload.get("attack_hypotheses"), allowed)
    recommendations = _recommendations(payload.get("recommended_next_steps"), allowed)
    llm_frameworks = _frameworks(payload.get("framework_mappings"), allowed)
    severity = _severity(payload.get("severity")) or _severity_from_items(all_items)
    confidence = _bounded_int(payload.get("confidence"), default=_confidence(all_items))

    return AnalysisResponse(
        mode=cast(Any, mode),
        status="completed",
        provider=completion.provider,
        model=completion.model,
        investigation_id=evidence.investigation_id,
        target_type=cast(Any, target_type),
        target_value=target_value,
        executive_summary=executive
        or CitedAnalysisText(
            text="No supported executive summary was generated.",
            citation_ids=fallback_citation,
        ),
        technical_summary=technical
        or CitedAnalysisText(
            text="No supported technical summary was generated.",
            citation_ids=fallback_citation,
        ),
        observed_indicators=indicators,
        suspicious_findings=suspicious,
        attack_hypotheses=hypotheses,
        severity=severity,
        confidence=confidence,
        recommended_next_steps=recommendations or _fallback_recommendations(all_items),
        framework_mappings=_merge_frameworks(llm_frameworks, framework_mappings),
        citations=citations_from_items(all_items),
        errors=[],
    )


def _fallback_response(
    *,
    evidence: EvidenceBundle,
    knowledge_items: list[EvidenceItem],
    framework_mappings: list[AnalysisFrameworkMapping],
    mode: str,
    completion: ProviderCompletion,
    target_type: str | None,
    target_value: str | None,
) -> AnalysisResponse:
    all_items = [*evidence.items, *knowledge_items]
    citation_ids = _first_citation(all_items)
    highest = _highest_risk_item(all_items)
    executive_text = (
        "AI provider output is unavailable, so this response summarizes stored "
        "investigation evidence only."
    )
    technical_text = (
        f"{len(evidence.items)} investigation evidence items and "
        f"{len(knowledge_items)} knowledge items were available for review."
    )
    if highest is not None:
        executive_text = f"Highest-priority evidence item: {highest.title}."
        citation_ids = [highest.id]
    return AnalysisResponse(
        mode=cast(Any, mode),
        status=completion.status,
        provider=completion.provider,
        model=completion.model,
        investigation_id=evidence.investigation_id,
        target_type=cast(Any, target_type),
        target_value=target_value,
        executive_summary=CitedAnalysisText(
            text=executive_text,
            citation_ids=citation_ids,
        ),
        technical_summary=CitedAnalysisText(
            text=technical_text,
            citation_ids=citation_ids,
        ),
        observed_indicators=_fallback_indicators(all_items),
        suspicious_findings=_fallback_findings(all_items),
        attack_hypotheses=_fallback_hypotheses(all_items),
        severity=_severity_from_items(all_items),
        confidence=_confidence(all_items),
        recommended_next_steps=_fallback_recommendations(all_items),
        framework_mappings=framework_mappings,
        citations=citations_from_items(all_items),
        errors=[completion.error] if completion.error else [],
    )


def _parse_llm_content(content: str) -> dict[str, Any] | None:
    clean = content.strip()
    if clean.startswith("```"):
        clean = clean.strip("`")
        if clean.lower().startswith("json"):
            clean = clean[4:].strip()
    try:
        payload = json.loads(clean)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _cited_text(value: object, allowed: set[str]) -> CitedAnalysisText | None:
    if isinstance(value, str):
        citations = sorted(allowed)[:1]
        return CitedAnalysisText(text=value, citation_ids=citations) if value else None
    if not isinstance(value, dict):
        return None
    text = value.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    citation_ids = _valid_citations(value.get("citation_ids"), allowed)
    if allowed and not citation_ids:
        return None
    return CitedAnalysisText(text=text.strip(), citation_ids=citation_ids)


def _cited_text_list(value: object, allowed: set[str]) -> list[CitedAnalysisText]:
    if not isinstance(value, list):
        return []
    items: list[CitedAnalysisText] = []
    for raw in value:
        item = _cited_text(raw, allowed)
        if item is not None:
            items.append(item)
    return items


def _recommendations(
    value: object,
    allowed: set[str],
) -> list[AnalysisRecommendation]:
    if not isinstance(value, list):
        return []
    items: list[AnalysisRecommendation] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        action = raw.get("action")
        rationale = raw.get("rationale")
        if not isinstance(action, str) or not isinstance(rationale, str):
            continue
        citations = _valid_citations(raw.get("citation_ids"), allowed)
        if allowed and not citations:
            continue
        items.append(
            AnalysisRecommendation(
                action=action.strip(),
                rationale=rationale.strip(),
                citation_ids=citations,
            )
        )
    return items


def _frameworks(value: object, allowed: set[str]) -> list[AnalysisFrameworkMapping]:
    if not isinstance(value, list):
        return []
    mappings: list[AnalysisFrameworkMapping] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        framework = raw.get("framework")
        control = raw.get("control")
        rationale = raw.get("rationale")
        if not all(isinstance(item, str) for item in (framework, control, rationale)):
            continue
        citations = _valid_citations(raw.get("citation_ids"), allowed)
        if allowed and not citations:
            continue
        mappings.append(
            AnalysisFrameworkMapping(
                framework=cast(str, framework).strip(),
                control=cast(str, control).strip(),
                rationale=cast(str, rationale).strip(),
                citation_ids=citations,
            )
        )
    return mappings


def _valid_citations(value: object, allowed: set[str]) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item in allowed]


def _severity(value: object) -> FindingSeverity | None:
    return value if value in _SEVERITY_RANK else None


def _severity_from_items(items: list[EvidenceItem]) -> FindingSeverity:
    severity: FindingSeverity = "info"
    for item in items:
        raw = item.metadata.get("severity")
        if raw in _SEVERITY_RANK and _SEVERITY_RANK[raw] > _SEVERITY_RANK[severity]:
            severity = cast(FindingSeverity, raw)
        risk = item.metadata.get("risk_score")
        if isinstance(risk, int):
            severity = _higher_severity(severity, _severity_from_risk(risk))
    return severity


def _severity_from_risk(risk: int) -> FindingSeverity:
    if risk >= 90:
        return "critical"
    if risk >= 65:
        return "high"
    if risk >= 35:
        return "medium"
    if risk >= 10:
        return "low"
    return "info"


def _higher_severity(
    current: FindingSeverity,
    candidate: FindingSeverity,
) -> FindingSeverity:
    return candidate if _SEVERITY_RANK[candidate] > _SEVERITY_RANK[current] else current


def _confidence(items: list[EvidenceItem]) -> int:
    scores = [
        value
        for item in items
        for value in [item.metadata.get("confidence_score")]
        if isinstance(value, int)
    ]
    if scores:
        return max(0, min(100, max(scores)))
    return 70 if items else 0


def _bounded_int(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return max(0, min(100, value))
    if isinstance(value, float):
        return max(0, min(100, int(value)))
    return default


def _fallback_indicators(items: list[EvidenceItem]) -> list[CitedAnalysisText]:
    indicators = [
        item for item in items if item.source_type in ("recon_entity", "threat_finding")
    ]
    return [
        CitedAnalysisText(text=item.title, citation_ids=[item.id])
        for item in indicators[:10]
    ]


def _fallback_findings(items: list[EvidenceItem]) -> list[CitedAnalysisText]:
    findings = [item for item in items if item.source_type == "finding"]
    return [
        CitedAnalysisText(text=item.title, citation_ids=[item.id])
        for item in findings[:10]
    ]


def _fallback_hypotheses(items: list[EvidenceItem]) -> list[CitedAnalysisText]:
    risky = [
        item
        for item in items
        if isinstance(item.metadata.get("risk_score"), int)
        and cast(int, item.metadata["risk_score"]) >= 50
    ]
    return [
        CitedAnalysisText(
            text=(
                "Validate whether the cited high-risk signal represents active "
                "exposure, abuse, or stale historical evidence."
            ),
            citation_ids=[item.id],
        )
        for item in risky[:3]
    ]


def _fallback_recommendations(
    items: list[EvidenceItem],
) -> list[AnalysisRecommendation]:
    if not items:
        return [
            AnalysisRecommendation(
                action="Collect investigation evidence before requesting analysis.",
                rationale=(
                    "The analyst layer requires stored findings, recon entities, "
                    "threat intelligence, or knowledge documents for grounding."
                ),
                citation_ids=[],
            )
        ]
    highest = _highest_risk_item(items) or items[0]
    return [
        AnalysisRecommendation(
            action="Validate and remediate the cited evidence item.",
            rationale=(
                "The recommendation is limited to the stored evidence and should "
                "be handled through authorized defensive remediation workflow."
            ),
            citation_ids=[highest.id],
        )
    ]


def _highest_risk_item(items: list[EvidenceItem]) -> EvidenceItem | None:
    scored = [
        item
        for item in items
        if isinstance(item.metadata.get("risk_score"), int)
        or item.metadata.get("severity") in _SEVERITY_RANK
    ]
    if not scored:
        return items[0] if items else None
    return sorted(scored, key=_risk_sort_key, reverse=True)[0]


def _risk_sort_key(item: EvidenceItem) -> tuple[int, int]:
    risk = item.metadata.get("risk_score")
    severity = item.metadata.get("severity")
    return (
        risk if isinstance(risk, int) else 0,
        _SEVERITY_RANK.get(cast(FindingSeverity, severity), 0)
        if severity in _SEVERITY_RANK
        else 0,
    )


def _first_citation(items: list[EvidenceItem]) -> list[str]:
    return [items[0].id] if items else []


def _merge_frameworks(
    llm_frameworks: list[AnalysisFrameworkMapping],
    deterministic: list[AnalysisFrameworkMapping],
) -> list[AnalysisFrameworkMapping]:
    merged: dict[tuple[str, str, tuple[str, ...]], AnalysisFrameworkMapping] = {}
    for mapping in [*llm_frameworks, *deterministic]:
        key = (mapping.framework, mapping.control, tuple(mapping.citation_ids))
        merged.setdefault(key, mapping)
    return list(merged.values())[:12]
