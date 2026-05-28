from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RiskCategory = Literal[
    "virustotal",
    "abuseipdb",
    "tls_health",
    "security_headers",
    "suspicious_technologies",
    "certificate_anomalies",
]
RiskBand = Literal["Low", "Medium", "High", "Critical"]

_CATEGORY_WEIGHTS: dict[RiskCategory, float] = {
    "virustotal": 0.35,
    "abuseipdb": 0.35,
    "tls_health": 0.15,
    "security_headers": 0.15,
    "suspicious_technologies": 0.10,
    "certificate_anomalies": 0.15,
}


@dataclass(frozen=True)
class RiskSignal:
    category: RiskCategory
    score: int
    description: str


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    band: RiskBand
    signals: list[str]


def risk_band_from_score(score: int) -> RiskBand:
    bounded = _bounded_score(score)
    if bounded <= 25:
        return "Low"
    if bounded <= 50:
        return "Medium"
    if bounded <= 75:
        return "High"
    return "Critical"


def calculate_risk_v2(signals: list[RiskSignal]) -> RiskAssessment:
    if not signals:
        return RiskAssessment(score=0, band="Low", signals=[])

    total_weight = 0.0
    weighted_score = 0.0
    descriptions: list[str] = []
    for signal in signals:
        weight = _CATEGORY_WEIGHTS[signal.category]
        weighted_score += _bounded_score(signal.score) * weight
        total_weight += weight
        descriptions.append(signal.description)

    score = round(weighted_score / total_weight) if total_weight else 0
    return RiskAssessment(
        score=score,
        band=risk_band_from_score(score),
        signals=descriptions,
    )


def _bounded_score(score: int) -> int:
    return max(0, min(100, score))
