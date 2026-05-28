from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.models.finding import Finding
from app.models.threat_finding import ThreatFinding
from app.schemas.timeline import TimelineEvent
from app.services.timeline.service import (
    TimelineFilters,
    _event_from_finding,
    _event_from_threat_finding,
    filter_timeline_events,
)


def test_timeline_service_maps_finding_severity_and_confidence() -> None:
    finding = Finding(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        title="Malicious VirusTotal score",
        description="Provider reputation exceeded the high threshold.",
        severity="high",
        confidence_score=85,
        risk_score=72,
        source="virustotal",
        raw_data={},
        normalized_data={},
        status="open",
        created_at=datetime(2026, 5, 28, tzinfo=UTC),
        updated_at=datetime(2026, 5, 28, tzinfo=UTC),
    )

    event = _event_from_finding(finding)

    assert event.event_type == "finding_created"
    assert event.severity == "high"
    assert event.confidence == 85
    assert event.related_finding_ids == [finding.id]


def test_timeline_service_maps_threat_risk_to_severity() -> None:
    entity_id = uuid.uuid4()
    threat_finding = ThreatFinding(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        recon_entity_id=entity_id,
        target_type="ip",
        target_value="203.0.113.10",
        provider="abuseipdb",
        status="completed",
        risk_score=91,
        confidence="high",
        verdict="critical",
        signals=["abuse_confidence:95"],
        normalized_data={},
        raw_data={},
        collected_at=datetime(2026, 5, 28, tzinfo=UTC),
    )

    event = _event_from_threat_finding(threat_finding)

    assert event.severity == "critical"
    assert event.confidence == 90
    assert event.related_entity_ids == [entity_id]


def test_timeline_service_filters_events() -> None:
    now = datetime(2026, 5, 28, tzinfo=UTC)
    events = [
        TimelineEvent(
            id="one",
            timestamp=now - timedelta(days=1),
            event_type="finding_created",
            severity="high",
            source="virustotal",
            title="Finding",
            summary="Finding summary",
            confidence=90,
        ),
        TimelineEvent(
            id="two",
            timestamp=now,
            event_type="report_generated",
            severity="info",
            source="report",
            title="Report",
            summary="Report summary",
            confidence=80,
        ),
    ]

    filtered = filter_timeline_events(
        events,
        TimelineFilters(
            severity="high",
            event_type="finding_created",
            start_date=now - timedelta(days=2),
            end_date=now,
            source="virustotal",
        ),
    )

    assert [event.id for event in filtered] == ["one"]

