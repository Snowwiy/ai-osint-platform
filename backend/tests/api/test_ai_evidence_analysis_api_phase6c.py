from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.models.lan_monitoring import LanAsset, LanAssetTelemetry, LanServiceObservation


@pytest.mark.asyncio
async def test_host_analysis_history_rerun_compare_and_secret_filtering(
    client, admin_headers, analyst_headers, db, monkeypatch
):
    from app.services.ai_analysis import service

    monkeypatch.setattr(service, "_knowledge", lambda _query: [])
    now = datetime.now(UTC)
    asset = LanAsset(
        id=uuid.uuid4(),
        ip_address="192.168.50.10",
        hostname="phase6c-test-host",
        asset_type="server_host",
        device_type="server",
        os_family="windows",
        first_seen=now - timedelta(days=30),
        last_seen=now,
        is_authorized=True,
    )
    db.add(asset)
    db.add_all(
        [
            LanAssetTelemetry(
                lan_asset_id=asset.id,
                cpu_percent=cpu,
                memory_percent=memory,
                disk_percent=disk,
                collected_at=now - age,
                event_metadata={"listening_tcp_ports": [443, 5432]},
            )
            for age, cpu, memory, disk in (
                (timedelta(minutes=5), 60, 88, 40),
                (timedelta(minutes=20), 50, 82, 40),
                (timedelta(minutes=40), 45, 78, 39),
                (timedelta(minutes=75), 20, 40, 38),
                (timedelta(minutes=90), 30, 45, 38),
                (timedelta(minutes=105), 35, 50, 37),
            )
        ]
    )
    db.add(
        LanServiceObservation(
            lan_asset_id=asset.id,
            ip_address=asset.ip_address,
            port=5432,
            protocol="tcp",
            service_name="postgresql",
            service_label="PostgreSQL",
            banner_hint="Bearer banner-secret-that-must-not-leak",
            confidence=70,
            status="open",
            observed_at=now,
            source="bounded_tcp_check",
        )
    )
    await db.commit()

    request_body = {
        "workflow": "host_resource",
        "window": "1h",
        "resource": "memory",
        "desktop_inventory": {
            "available": True,
            "processes": [
                {
                    "pid": 42,
                    "name": "browser password=process-secret",
                    "cpuPercent": 4.0,
                    "memoryBytes": 1_000_000_000,
                    "startedAtUnix": int((now - timedelta(minutes=12)).timestamp()),
                    "runtimeSeconds": 720,
                    "command_line": "--api-key never-persist-this",
                }
            ],
        },
    }
    denied = await client.post(
        "/api/v1/ai/analysis/run",
        headers=analyst_headers,
        json=request_body,
    )
    assert denied.status_code == 403

    first = await client.post(
        "/api/v1/ai/analysis/run", headers=admin_headers, json=request_body
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    result_text = first.text
    assert first_body["workflow"] == "host_resource"
    assert first_body["result"]["metrics"]["memory"]["current"] == 88.0
    assert first_body["result"]["hypotheses"][0]["causality_confirmed"] is False
    assert "browser [redacted]" in result_text
    assert "process-secret" not in result_text
    assert "never-persist-this" not in result_text
    assert "banner-secret-that-must-not-leak" not in result_text
    assert "command_line" not in result_text
    assert len(first_body["bundle_sha256"]) == 64

    repeated = await client.post(
        "/api/v1/ai/analysis/run", headers=admin_headers, json=request_body
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["deduplicated"] is True
    assert repeated.json()["id"] == first_body["id"]

    history = await client.get("/api/v1/ai/analysis/history", headers=admin_headers)
    assert history.status_code == 200
    assert any(item["id"] == first_body["id"] for item in history.json())

    rerun = await client.post(
        f"/api/v1/ai/analysis/{first_body['id']}/rerun", headers=admin_headers
    )
    assert rerun.status_code == 200, rerun.text
    assert rerun.json()["id"] != first_body["id"]
    comparison = await client.post(
        "/api/v1/ai/analysis/compare",
        headers=admin_headers,
        json={
            "first_analysis_id": first_body["id"],
            "second_analysis_id": rerun.json()["id"],
        },
    )
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["same_bundle"] is False


@pytest.mark.asyncio
async def test_asset_analysis_is_scoped_and_history_is_user_owned(
    client, analyst_headers, admin_headers, analyst_user, other_user, db, monkeypatch
):
    from app.models.operational_analysis import OperationalAnalysis
    from app.services.ai_analysis import service

    monkeypatch.setattr(service, "_knowledge", lambda _query: [])
    asset = LanAsset(
        id=uuid.uuid4(),
        ip_address="192.168.50.77",
        hostname="phase6c-asset",
        asset_type="lan_endpoint",
        device_type="unknown",
        os_family="unknown",
        first_seen=datetime.now(UTC) - timedelta(days=2),
        last_seen=datetime.now(UTC),
    )
    db.add(asset)
    await db.flush()
    row = OperationalAnalysis(
        requested_by_user_id=other_user.id,
        workflow="asset_current",
        scope_type="asset",
        scope_id=str(asset.id),
        status="completed",
        summary="Other user's analysis",
        confidence="low",
        evidence_count=0,
        window={},
        evidence_ids=[],
        result={},
        model_metadata={"mode": "deterministic"},
        bundle_sha256="a" * 64,
        dedupe_key="b" * 64,
    )
    db.add(row)
    await db.commit()

    response = await client.post(
        "/api/v1/ai/analysis/run",
        headers=analyst_headers,
        json={"workflow": "asset_current", "scope_id": str(asset.id)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"]["scope"]["id"] == str(asset.id)
    history = await client.get("/api/v1/ai/analysis/history", headers=analyst_headers)
    assert history.status_code == 200
    assert all(item["id"] != str(row.id) for item in history.json())
    forbidden_detail = await client.get(
        f"/api/v1/ai/analysis/{row.id}", headers=analyst_headers
    )
    assert forbidden_detail.status_code == 404

    malformed = await client.post(
        "/api/v1/ai/analysis/run",
        headers=admin_headers,
        json={"workflow": "posture_context"},
    )
    assert malformed.status_code == 422
