from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.ai_analysis import AnalysisWindow, Confidence, ResourceKind

WINDOWS: dict[AnalysisWindow, timedelta] = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}
MAX_EVIDENCE = 250
MAX_BUNDLE_BYTES = 64_000


class TimeWindow(BaseModel):
    start_at: datetime
    end_at: datetime
    baseline_start_at: datetime
    baseline_end_at: datetime
    label: str


class MetricSample(BaseModel):
    observed_at: datetime
    value: float


class MetricTrend(BaseModel):
    metric: ResourceKind
    current: float | None
    average: float | None
    minimum: float | None
    maximum: float | None
    delta_from_baseline: float | None
    trend: Literal["rising", "falling", "stable", "unknown"]
    sample_count: int = Field(ge=0)
    baseline_sample_count: int = Field(ge=0)
    baseline_status: Literal["available", "insufficient_data"]
    current_observed_at: datetime | None


def normalize_time_window(
    window: AnalysisWindow,
    *,
    now: datetime | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> TimeWindow:
    current = _aware(now or datetime.now(UTC))
    if start_at is not None and end_at is not None:
        start, end = _aware(start_at), _aware(end_at)
        if end > current + timedelta(minutes=1):
            raise ValueError("Analysis end time cannot be in the future.")
        if end <= start or end - start > timedelta(days=7):
            raise ValueError("Explicit analysis windows must be at most seven days.")
        duration = end - start
        label = "explicit"
    else:
        duration = WINDOWS[window]
        end = current
        start = end - duration
        label = window
    baseline_start = start - min(duration, timedelta(days=7))
    return TimeWindow(
        start_at=start,
        end_at=end,
        baseline_start_at=baseline_start,
        baseline_end_at=start,
        label=label,
    )


def metric_trend(
    metric: ResourceKind,
    current_samples: Sequence[MetricSample],
    baseline_samples: Sequence[MetricSample],
) -> MetricTrend:
    current_rows = sorted(current_samples, key=lambda item: item.observed_at)
    baseline_rows = sorted(baseline_samples, key=lambda item: item.observed_at)
    baseline_values = [item.value for item in baseline_rows]
    current = current_rows[-1] if current_rows else None
    enough = len(baseline_rows) >= 3
    average = sum(baseline_values) / len(baseline_values) if enough else None
    values = [item.value for item in current_rows]
    trend: Literal["rising", "falling", "stable", "unknown"] = "unknown"
    if len(values) >= 3:
        difference = values[-1] - values[0]
        tolerance = max(1.0, abs(values[0]) * 0.05)
        trend = (
            "rising"
            if difference > tolerance
            else "falling"
            if difference < -tolerance
            else "stable"
        )
    return MetricTrend(
        metric=metric,
        current=round(current.value, 2) if current else None,
        average=round(average, 2) if average is not None else None,
        minimum=round(min(baseline_values), 2) if enough else None,
        maximum=round(max(baseline_values), 2) if enough else None,
        delta_from_baseline=(
            round(current.value - average, 2)
            if current is not None and average is not None
            else None
        ),
        trend=trend,
        sample_count=len(current_rows),
        baseline_sample_count=len(baseline_rows),
        baseline_status="available" if enough else "insufficient_data",
        current_observed_at=current.observed_at if current else None,
    )


def bundle_hash(payload: dict[str, Any]) -> str:
    normalized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def correlate_changes(changes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = sorted(
        (item for item in changes if item.get("observed_at")),
        key=lambda item: (_aware(item["observed_at"]), str(item.get("id", ""))),
    )
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in normalized:
        key = str(item.get("id") or bundle_hash(item))
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    clusters: list[list[dict[str, Any]]] = []
    for item in deduped:
        timestamp = _aware(item["observed_at"])
        scope = str(item.get("scope_id") or "global")
        if clusters:
            prior = clusters[-1][-1]
            prior_scope = str(prior.get("scope_id") or "global")
            prior_time = _aware(prior["observed_at"])
            if scope == prior_scope and timestamp - prior_time <= timedelta(minutes=5):
                clusters[-1].append(item)
                continue
        clusters.append([item])

    results: list[dict[str, Any]] = []
    for group in clusters:
        if len(group) < 2:
            continue
        kinds = sorted({str(item.get("kind", "change")) for item in group})
        sources = {str(item.get("source", "unknown")) for item in group}
        confidence: Confidence = (
            "high" if len(sources) >= 3 else "medium" if len(sources) >= 2 else "low"
        )
        severity = max(
            (_severity_rank(str(item.get("severity", "info"))) for item in group),
            default=0,
        )
        results.append(
            {
                "correlation_id": str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        "|".join(sorted(str(item.get("id", "")) for item in group)),
                    )
                ),
                "title": "Related operational changes",
                "scope_id": group[0].get("scope_id"),
                "start_at": _aware(group[0]["observed_at"]).isoformat(),
                "end_at": _aware(group[-1]["observed_at"]).isoformat(),
                "evidence_ids": [str(item.get("id")) for item in group],
                "categories": kinds,
                "severity": _severity_name(severity),
                "confidence": confidence,
                "reason": (
                    f"{len(group)} observations from {len(sources)} source category(s) "
                    "occurred within five minutes. "
                    "Temporal correlation does not prove causality."
                ),
            }
        )
    return results[:50]


def compare_port_sets(
    current_ports: set[int], previous_ports: set[int] | None
) -> list[dict[str, str | int]]:
    """Return listener transitions only when a prior sample exists."""
    if previous_ports is None:
        return []
    return [
        {
            "port": port,
            "state": "open" if port in current_ports else "closed",
            "kind": "port_opened" if port in current_ports else "port_closed",
        }
        for port in sorted(current_ports ^ previous_ports)
    ]


def classify_confidence(
    *, evidence_count: int, source_count: int, gaps: Sequence[str], stale: bool = False
) -> Confidence:
    if evidence_count == 0:
        return "insufficient"
    if stale or (not source_count and gaps):
        return "low"
    if source_count >= 3 and evidence_count >= 5 and not gaps:
        return "high"
    if source_count >= 2 and evidence_count >= 2:
        return "medium"
    return "low"


def metric_hypotheses(
    *,
    metric: MetricTrend,
    processes: Sequence[dict[str, Any]],
    evidence: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    threshold = {"cpu": 85.0, "memory": 85.0, "disk": 90.0}[metric.metric]
    if metric.current is None or metric.current < threshold:
        return []
    if (
        metric.baseline_status == "available"
        and metric.delta_from_baseline is not None
        and metric.delta_from_baseline < 5
    ):
        return []
    if metric.metric == "disk":
        return []
    ordered = sorted(
        processes,
        key=lambda item: (
            float(item.get("memory_bytes", 0))
            if metric.metric == "memory"
            else float(item.get("cpu_percent", 0))
        ),
        reverse=True,
    )
    if not ordered:
        return []
    contributor = ordered[0]
    process_id = str(contributor.get("evidence_id", ""))
    supporting = [
        str(item.get("id", ""))
        for item in evidence
        if item.get("kind") == "metric_sample"
    ][-3:]
    if process_id:
        supporting.append(process_id)
    contradicting: list[str] = []
    temporal_relation = "No process start-time relationship could be established."
    started_at = contributor.get("started_at")
    if metric.current_observed_at is not None and isinstance(started_at, str):
        try:
            process_started = _aware(started_at)
        except ValueError:
            process_started = None
        if process_started is not None:
            if process_started > metric.current_observed_at:
                temporal_relation = (
                    "The process started after the latest elevated metric sample; "
                    "it cannot explain that earlier observation."
                )
                if process_id:
                    contradicting.append(process_id)
            elif metric.current_observed_at - process_started <= timedelta(minutes=10):
                temporal_relation = (
                    "The process start and elevated metric sample occurred within "
                    "ten minutes; this is temporal correlation only."
                )
    label = (
        "possible contributor"
        if metric.metric == "memory"
        else "possible current contributor"
    )
    return [
        {
            "candidate": (
                f"Process {str(contributor.get('name', 'unknown'))[:160]} may "
                f"contribute to elevated {metric.metric} usage."
            ),
            "label": label,
            "confidence": "low" if metric.baseline_status != "available" else "medium",
            "supporting_evidence": supporting,
            "contradicting_evidence": contradicting,
            "temporal_relation": temporal_relation,
            "missing_evidence": [
                "Historical per-process resource samples are not stored, so "
                "contribution over time cannot be confirmed."
            ],
            "causality_confirmed": False,
        }
    ]


def _severity_rank(value: str) -> int:
    return {
        "info": 0,
        "low": 1,
        "medium": 2,
        "warning": 3,
        "high": 4,
        "critical": 5,
    }.get(value.casefold(), 0)


def _severity_name(value: int) -> str:
    return {
        0: "informational",
        1: "informational",
        2: "notable",
        3: "warning",
        4: "warning",
        5: "critical",
    }.get(value, "informational")


def _aware(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return _aware(value).isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"Unsupported bundle value: {type(value).__name__}")
