from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from app.schemas.ai_analysis import DesktopAnalysisInventory, EvidenceAnalysisRequest
from app.services.ai_analysis.engine import (
    MetricSample,
    bundle_hash,
    classify_confidence,
    compare_port_sets,
    correlate_changes,
    metric_hypotheses,
    metric_trend,
    normalize_time_window,
)
from app.services.ai_analysis.service import (
    AnalysisAccessError,
    AnalysisNotFoundError,
    build_bundle,
    compare_analysis_rows,
    create_analysis,
    get_analysis,
)
from pydantic import ValidationError


def test_explicit_windows_are_bounded_and_have_matched_baseline() -> None:
    now = datetime(2026, 9, 25, 12, tzinfo=UTC)
    window = normalize_time_window(
        "1h",
        now=now,
        start_at=now - timedelta(hours=3),
        end_at=now - timedelta(hours=2),
    )
    assert window.label == "explicit"
    assert window.start_at == now - timedelta(hours=3)
    assert window.baseline_end_at == window.start_at
    assert window.baseline_start_at == now - timedelta(hours=4)
    with pytest.raises(ValueError, match="seven days"):
        normalize_time_window(
            "1h",
            now=now,
            start_at=now - timedelta(days=8),
            end_at=now,
        )


def test_metric_trend_does_not_claim_baseline_from_one_sample() -> None:
    now = datetime(2026, 9, 25, 12, tzinfo=UTC)
    trend = metric_trend(
        "memory",
        [
            MetricSample(observed_at=now - timedelta(minutes=5), value=60),
            MetricSample(observed_at=now - timedelta(minutes=2), value=82),
            MetricSample(observed_at=now, value=90),
        ],
        [MetricSample(observed_at=now - timedelta(hours=1), value=40)],
    )
    assert trend.current == 90
    assert trend.trend == "rising"
    assert trend.baseline_status == "insufficient_data"
    assert trend.average is None
    assert trend.delta_from_baseline is None


def test_metric_trend_reports_baseline_and_direction_when_supported() -> None:
    now = datetime(2026, 9, 25, 12, tzinfo=UTC)
    trend = metric_trend(
        "cpu",
        [
            MetricSample(observed_at=now - timedelta(minutes=4), value=20),
            MetricSample(observed_at=now - timedelta(minutes=2), value=24),
            MetricSample(observed_at=now, value=30),
        ],
        [
            MetricSample(observed_at=now - timedelta(hours=3), value=10),
            MetricSample(observed_at=now - timedelta(hours=2), value=20),
            MetricSample(observed_at=now - timedelta(hours=1), value=30),
        ],
    )
    assert trend.average == 20
    assert trend.delta_from_baseline == 10
    assert trend.baseline_status == "available"
    assert trend.trend == "rising"


def test_temporal_correlation_deduplicates_and_does_not_assert_causality() -> None:
    observed = datetime(2026, 9, 25, 12, tzinfo=UTC).isoformat()
    changes = [
        {
            "id": "service-1",
            "kind": "service_stopped",
            "scope_id": "asset-a",
            "source": "service_history",
            "observed_at": observed,
            "severity": "warning",
        },
        {
            "id": "alert-1",
            "kind": "alert_created",
            "scope_id": "asset-a",
            "source": "alerts",
            "observed_at": (
                datetime.fromisoformat(observed) + timedelta(minutes=2)
            ).isoformat(),
            "severity": "critical",
        },
        {
            "id": "alert-1",
            "kind": "alert_created",
            "scope_id": "asset-a",
            "source": "alerts",
            "observed_at": (
                datetime.fromisoformat(observed) + timedelta(minutes=2)
            ).isoformat(),
            "severity": "critical",
        },
    ]
    groups = correlate_changes(changes)
    assert len(groups) == 1
    assert groups[0]["confidence"] == "medium"
    assert groups[0]["severity"] == "critical"
    assert "does not prove causality" in groups[0]["reason"]
    assert groups[0]["evidence_ids"] == ["service-1", "alert-1"]


def test_confidence_reflects_evidence_gaps_and_source_independence() -> None:
    assert (
        classify_confidence(evidence_count=0, source_count=0, gaps=[]) == "insufficient"
    )
    assert classify_confidence(evidence_count=2, source_count=2, gaps=[]) == "medium"
    assert classify_confidence(evidence_count=6, source_count=3, gaps=[]) == "high"
    assert (
        classify_confidence(
            evidence_count=6, source_count=3, gaps=["stale"], stale=True
        )
        == "low"
    )


def test_resource_candidate_is_a_hypothesis_not_a_confirmed_cause() -> None:
    trend = metric_trend(
        "memory",
        [
            MetricSample(
                observed_at=datetime.now(UTC) - timedelta(minutes=3), value=88
            ),
            MetricSample(
                observed_at=datetime.now(UTC) - timedelta(minutes=2), value=90
            ),
            MetricSample(observed_at=datetime.now(UTC), value=92),
        ],
        [],
    )
    candidates = metric_hypotheses(
        metric=trend,
        processes=[
            {"name": "browser", "memory_bytes": 2_000_000, "evidence_id": "p:1"}
        ],
        evidence=[],
    )
    assert len(candidates) == 1
    assert candidates[0]["confidence"] == "low"
    assert candidates[0]["causality_confirmed"] is False
    assert candidates[0]["contradicting_evidence"] == []
    assert (
        "Historical per-process resource samples"
        in candidates[0]["missing_evidence"][0]
    )


def test_bundle_hash_is_stable_for_identical_evidence() -> None:
    payload = {"facts": [{"id": "metric:cpu", "value": 25}], "truncated": False}
    assert bundle_hash(payload) == bundle_hash(payload)
    assert bundle_hash(payload) != bundle_hash({**payload, "truncated": True})


def test_port_changes_require_a_comparable_previous_observation() -> None:
    assert compare_port_sets({22, 443}, None) == []
    assert compare_port_sets({22, 443}, {22, 80}) == [
        {"port": 80, "state": "closed", "kind": "port_closed"},
        {"port": 443, "state": "open", "kind": "port_opened"},
    ]


def test_process_started_after_metric_is_contradicting_evidence() -> None:
    observed_at = datetime(2026, 9, 25, 12, tzinfo=UTC)
    trend = metric_trend(
        "cpu",
        [
            MetricSample(observed_at=observed_at - timedelta(minutes=4), value=80),
            MetricSample(observed_at=observed_at - timedelta(minutes=2), value=90),
            MetricSample(observed_at=observed_at, value=95),
        ],
        [],
    )
    candidate = metric_hypotheses(
        metric=trend,
        processes=[
            {
                "name": "late process",
                "cpu_percent": 96,
                "evidence_id": "process:late",
                "started_at": (observed_at + timedelta(minutes=2)).isoformat(),
            }
        ],
        evidence=[],
    )[0]
    assert candidate["contradicting_evidence"] == ["process:late"]
    assert "started after" in candidate["temporal_relation"]
    assert candidate["causality_confirmed"] is False


def test_result_sanitizer_redacts_bearers_jwts_and_provider_key_shapes() -> None:
    from app.services.ai_analysis.service import _clean

    values = (
        "Bearer private-token eyJabcdefghijk.abcdefghijk.abcdefghijk "
        "sk-proj-12345678901234567890\n-----BEGIN PRIVATE KEY-----\n"
        "private-key-body\n-----END PRIVATE KEY-----\n"
        "-----BEGIN PGP PRIVATE KEY BLOCK-----\npgp-key-body\n"
        "-----END PGP PRIVATE KEY BLOCK-----"
    )
    cleaned = _clean(values, 500)
    assert "private-token" not in cleaned
    assert "eyJabcdefghijk" not in cleaned
    assert "sk-proj-12345678901234567890" not in cleaned
    assert "private-key-body" not in cleaned
    assert "pgp-key-body" not in cleaned


def test_inventory_drops_command_lines_and_request_rejects_unbounded_shape() -> None:
    inventory = DesktopAnalysisInventory.model_validate(
        {
            "available": True,
            "processes": [
                {
                    "pid": 11,
                    "name": "safe process",
                    "cpuPercent": 1.5,
                    "memoryBytes": 4096,
                    "startedAtUnix": 1,
                    "runtimeSeconds": 3,
                    "command_line": "--password do-not-persist",
                }
            ],
        }
    )
    serialized = inventory.model_dump_json()
    assert "command_line" not in serialized
    assert "do-not-persist" not in serialized
    with pytest.raises(ValidationError):
        EvidenceAnalysisRequest.model_validate(
            {"workflow": "host_current", "arbitrary_query": "select * from users"}
        )
    with pytest.raises(ValidationError):
        EvidenceAnalysisRequest.model_validate(
            {"workflow": "execute_python", "window": "1h"}
        )


@pytest.mark.asyncio
async def test_admin_required_for_desktop_inventory() -> None:
    user = SimpleNamespace(role="analyst", id=uuid.uuid4())
    request = EvidenceAnalysisRequest(
        workflow="host_current",
        desktop_inventory=DesktopAnalysisInventory(available=True),
    )

    with pytest.raises(AnalysisAccessError):
        await create_analysis(object(), user, request)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_analysis_api_audits_only_sanitized_result_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1 import ai_analysis as api

    user_id, row_id = uuid.uuid4(), uuid.uuid4()
    row = SimpleNamespace(
        id=row_id,
        workflow="host_current",
        scope_type="host",
        scope_id=None,
        created_at=datetime(2026, 9, 25, 12, tzinfo=UTC),
        window={"label": "1h"},
        status="completed",
        summary="Evidence summary",
        confidence="low",
        evidence_count=1,
        bundle_sha256="a" * 64,
        result={"sensitive_example": "should-not-enter-audit"},
        model_metadata={"mode": "deterministic"},
    )
    audit_events: list[dict[str, object]] = []

    async def fake_create_analysis(_db, _user, _request):
        return row, False

    async def fake_record_event(_db, **kwargs):
        audit_events.append(kwargs)

    class EmptySession:
        async def commit(self) -> None:
            return None

        async def refresh(self, _row: object) -> None:
            return None

    monkeypatch.setattr(api, "create_analysis", fake_create_analysis)
    monkeypatch.setattr(api, "record_event", fake_record_event)

    response = await api.run_evidence_analysis(
        EvidenceAnalysisRequest(workflow="host_current"),
        SimpleNamespace(id=user_id, role="analyst"),  # type: ignore[arg-type]
        EmptySession(),  # type: ignore[arg-type]
    )

    assert response.id == row_id
    assert len(audit_events) == 1
    audit_metadata = audit_events[0]["metadata"]
    assert isinstance(audit_metadata, dict)
    assert audit_metadata["evidence_count"] == 1
    assert "sensitive_example" not in audit_metadata
    assert "should-not-enter-audit" not in str(audit_metadata)


@pytest.mark.asyncio
async def test_analysis_history_detail_is_owner_scoped() -> None:
    owner_id, other_id = uuid.uuid4(), uuid.uuid4()
    analysis_id = uuid.uuid4()
    row = SimpleNamespace(id=analysis_id, requested_by_user_id=owner_id)

    class RowSession:
        async def get(self, _model: object, identity: object) -> object | None:
            return row if identity == analysis_id else None

    assert (
        await get_analysis(
            RowSession(),
            SimpleNamespace(id=owner_id, role="analyst"),
            analysis_id,  # type: ignore[arg-type]
        )
        is row
    )
    with pytest.raises(AnalysisNotFoundError):
        await get_analysis(
            RowSession(),
            SimpleNamespace(id=other_id, role="analyst"),
            analysis_id,  # type: ignore[arg-type]
        )


def test_analysis_api_rejects_roles_outside_analyst_or_admin() -> None:
    from app.api.v1.ai_analysis import _require_analyst
    from fastapi import HTTPException

    _require_analyst(SimpleNamespace(role="admin"))  # type: ignore[arg-type]
    _require_analyst(SimpleNamespace(role="analyst"))  # type: ignore[arg-type]
    with pytest.raises(HTTPException) as error:
        _require_analyst(SimpleNamespace(role="viewer"))  # type: ignore[arg-type]
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_host_bundle_without_database_evidence_reports_gaps_not_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.ai_analysis import service

    class EmptyScalars:
        def all(self) -> list[object]:
            return []

    class EmptyResult:
        def scalar_one_or_none(self) -> None:
            return None

        def scalars(self) -> EmptyScalars:
            return EmptyScalars()

    class EmptySession:
        async def execute(self, _statement: object) -> EmptyResult:
            return EmptyResult()

        async def get(self, _model: object, _identity: object) -> None:
            return None

    monkeypatch.setattr(service, "_knowledge", lambda _query: [])
    now = datetime(2026, 9, 25, 12, tzinfo=UTC)
    request = EvidenceAnalysisRequest(workflow="host_current", window="1h")
    window = normalize_time_window("1h", now=now)

    bundle = await build_bundle(EmptySession(), object(), request, window, now)  # type: ignore[arg-type]

    assert bundle["metrics"] == {}
    assert bundle["processes"] == []
    assert bundle["services"] == []
    assert bundle["ports"] == []
    assert bundle["changes"] == []
    assert bundle["facts"] == []
    assert bundle["confidence"] == "insufficient"
    assert any("No primary ServerHost" in gap for gap in bundle["data_gaps"])
    assert any("No primary host metric history" in gap for gap in bundle["data_gaps"])


def test_analysis_comparison_reports_metric_and_evidence_differences() -> None:
    first = SimpleNamespace(
        id=uuid.uuid4(),
        bundle_sha256="a" * 64,
        confidence="low",
        evidence_count=1,
        summary="Earlier summary",
        result={
            "metrics": {"memory": {"current": 72.0, "trend": "stable"}},
            "bundle": {
                "facts": [{"id": "metric:old", "title": "Memory sample"}],
                "changes": [],
                "data_gaps": ["Old history missing"],
            },
        },
    )
    second = SimpleNamespace(
        id=uuid.uuid4(),
        bundle_sha256="b" * 64,
        confidence="medium",
        evidence_count=2,
        summary="Later summary",
        result={
            "metrics": {"memory": {"current": 91.0, "trend": "rising"}},
            "bundle": {
                "facts": [{"id": "metric:new", "title": "Memory sample"}],
                "changes": [
                    {
                        "id": "service:new",
                        "title": "Service observed password=do-not-leak",
                    }
                ],
                "data_gaps": ["Recent process history missing"],
            },
        },
    )

    comparison = compare_analysis_rows(first, second)  # type: ignore[arg-type]

    assert comparison["same_bundle"] is False
    differences = comparison["differences"]
    assert any(
        "memory current changed from 72.0 to 91.0" in item for item in differences
    )
    assert any(
        "memory trend changed from stable to rising" in item for item in differences
    )
    assert any(
        "New timeline change: Service observed [redacted]" in item
        for item in differences
    )
    assert "do-not-leak" not in " ".join(differences)
    assert any("Evidence gap added" in item for item in differences)
