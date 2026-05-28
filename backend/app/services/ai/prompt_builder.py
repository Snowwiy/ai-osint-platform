from __future__ import annotations

from app.schemas.analysis import AnalysisFrameworkMapping, AnalysisMode, IocType
from app.services.ai.evidence_builder import EvidenceItem

_SYSTEM_INSTRUCTIONS = "\n".join(
    (
        "You are a defensive cybersecurity analyst.",
        "Use only the evidence IDs and knowledge snippets supplied in the prompt.",
        "Do not invent facts, indicators, frameworks, controls, or mitigations.",
        "Do not provide offensive procedures, exploitation steps, crawling, "
        "scanning, or attack automation.",
        "Every substantive claim must include one or more citation_ids from the "
        "supplied evidence.",
        "Return strict JSON only.",
    )
)


def build_analysis_prompt(
    *,
    mode: AnalysisMode,
    evidence_items: list[EvidenceItem],
    knowledge_items: list[EvidenceItem],
    framework_mappings: list[AnalysisFrameworkMapping],
    target_type: IocType | None = None,
    target_value: str | None = None,
) -> str:
    sections = [
        _SYSTEM_INSTRUCTIONS,
        "",
        f"Analysis mode: {mode}",
    ]
    if target_type and target_value:
        sections.append(f"IOC target: {target_type}={target_value}")
    sections.extend(
        [
            "",
            "Required JSON shape:",
            _json_shape(),
            "",
            "Evidence:",
            *_format_items(evidence_items),
            "",
            "Knowledge context:",
            *_format_items(knowledge_items),
            "",
            "Deterministic framework candidates:",
            *_format_frameworks(framework_mappings),
            "",
            "Severity must be one of: info, low, medium, high, critical.",
            "Confidence must be an integer from 0 to 100.",
        ]
    )
    return "\n".join(sections)


def _json_shape() -> str:
    return (
        "{"
        '"executive_summary":{"text":"...","citation_ids":["evidence:id"]},'
        '"technical_summary":{"text":"...","citation_ids":["evidence:id"]},'
        '"observed_indicators":[{"text":"...","citation_ids":["evidence:id"]}],'
        '"suspicious_findings":[{"text":"...","citation_ids":["evidence:id"]}],'
        '"attack_hypotheses":[{"text":"...","citation_ids":["evidence:id"]}],'
        '"severity":"medium",'
        '"confidence":75,'
        '"recommended_next_steps":[{"action":"...","rationale":"...",'
        '"citation_ids":["evidence:id"]}],'
        '"framework_mappings":[{"framework":"...","control":"...",'
        '"rationale":"...","citation_ids":["evidence:id"]}]'
        "}"
    )


def _format_items(items: list[EvidenceItem]) -> list[str]:
    if not items:
        return ["- none"]
    return [
        f"- {item.id} | {item.source_type} | {item.title} | {item.summary[:600]}"
        for item in items[:40]
    ]


def _format_frameworks(mappings: list[AnalysisFrameworkMapping]) -> list[str]:
    if not mappings:
        return ["- none"]
    return [
        (
            f"- {mapping.framework} | {mapping.control} | "
            f"citations={','.join(mapping.citation_ids)} | {mapping.rationale}"
        )
        for mapping in mappings[:20]
    ]
