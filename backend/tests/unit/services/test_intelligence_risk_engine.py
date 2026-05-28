from __future__ import annotations

from app.services.intelligence.risk_engine import (
    RiskSignal,
    calculate_risk_v2,
    risk_band_from_score,
)


def test_risk_band_boundaries() -> None:
    assert risk_band_from_score(0) == "Low"
    assert risk_band_from_score(25) == "Low"
    assert risk_band_from_score(26) == "Medium"
    assert risk_band_from_score(50) == "Medium"
    assert risk_band_from_score(51) == "High"
    assert risk_band_from_score(75) == "High"
    assert risk_band_from_score(76) == "Critical"
    assert risk_band_from_score(100) == "Critical"


def test_calculate_risk_v2_uses_weighted_reputation_and_health_signals() -> None:
    assessment = calculate_risk_v2(
        [
            RiskSignal(category="virustotal", score=80, description="VT malicious"),
            RiskSignal(category="abuseipdb", score=70, description="AbuseIPDB high"),
            RiskSignal(category="tls_health", score=50, description="Expired cert"),
            RiskSignal(
                category="security_headers",
                score=30,
                description="Missing HSTS",
            ),
        ]
    )

    assert assessment.score == 64
    assert assessment.band == "High"
    assert assessment.signals == [
        "VT malicious",
        "AbuseIPDB high",
        "Expired cert",
        "Missing HSTS",
    ]


def test_calculate_risk_v2_returns_low_when_no_signals_exist() -> None:
    assessment = calculate_risk_v2([])

    assert assessment.score == 0
    assert assessment.band == "Low"
    assert assessment.signals == []
