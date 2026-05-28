from __future__ import annotations

from app.schemas.threat_intel import Confidence, RiskLevel


def confidence_from_score(score: int) -> Confidence:
    if score >= 70:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def risk_level_from_score(score: int) -> RiskLevel:
    if score >= 90:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def verdict_from_score(score: int) -> RiskLevel | str:
    if score <= 0:
        return "clean"
    return risk_level_from_score(score)
