from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from app.models.endpoint_posture import (
    EndpointRemediationRecommendation,
    EndpointSecurityPosture,
)
from app.models.lan_monitoring import LanAsset, LanAssetTelemetry, LanServiceObservation
from app.models.target import Target
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def test_unauthorized_asset_creates_manual_isolation_recommendation(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    asset = LanAsset(
        ip_address="192.168.0.210",
        hostname="unknown-device",
        status="online",
        source="router",
        is_authorized=False,
        monitoring_enabled=True,
    )
    db.add(asset)
    await db.commit()

    assessed = await client.post(
        f"/api/v1/monitoring/lan/assets/{asset.id}/posture/assess",
        headers=admin_headers,
    )
    recommendations = await client.get(
        "/api/v1/monitoring/recommendations",
        headers=admin_headers,
        params={"asset_id": str(asset.id)},
    )

    assert assessed.status_code == 200
    assert assessed.json()["posture_status"] == "at_risk"
    assert 0 <= assessed.json()["posture_score"] <= 60
    item = recommendations.json()["items"][0]
    assert item["isolation_recommended"] is True
    assert "manually" in item["recommended_action"].lower()
    assert "router" in " ".join(item["manual_steps"]).lower()


async def test_agent_posture_detects_stale_firewall_and_patch_risks(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    asset = LanAsset(
        ip_address="192.168.0.211",
        hostname="managed-endpoint",
        criticality="critical",
        status="online",
        source="agent",
        is_authorized=True,
        monitoring_enabled=True,
    )
    db.add(asset)
    await db.flush()
    db.add(
        LanAssetTelemetry(
            lan_asset_id=asset.id,
            cpu_percent=25,
            memory_percent=40,
            disk_percent=75,
            uptime_seconds=9000,
            os_name="Windows 11 Enterprise",
            os_version="10.0",
            agent_version="1.1.0",
            collected_at=datetime.now(UTC) - timedelta(minutes=30),
            event_metadata={
                "firewall_status": "disabled",
                "antivirus_status": "disabled",
                "patch_status": "stale",
                "pending_reboot": True,
                "listening_tcp_ports": [5432],
                "token": "must-not-be-returned",
            },
        )
    )
    await db.commit()

    assessed = await client.post(
        f"/api/v1/monitoring/lan/assets/{asset.id}/posture/assess",
        headers=admin_headers,
    )
    recommendations = await client.get(
        "/api/v1/monitoring/recommendations",
        headers=admin_headers,
        params={"asset_id": str(asset.id)},
    )

    assert assessed.status_code == 200
    body = assessed.json()
    assert body["firewall_status"] == "disabled"
    assert body["patch_status"] == "stale"
    assert body["agent_freshness"] == "stale"
    titles = {item["title"] for item in recommendations.json()["items"]}
    assert "Restore endpoint-agent reporting" in titles
    assert "Enable endpoint firewall" in titles
    assert "Review endpoint patch posture" in titles
    assert "Review exposed PostgreSQL service" in titles
    assert "must-not-be-returned" not in json.dumps(body)
    assert "must-not-be-returned" not in recommendations.text


async def test_risky_service_and_recommendation_lifecycle(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    asset = LanAsset(
        ip_address="192.168.0.212",
        status="online",
        source="static",
        is_authorized=True,
        monitoring_enabled=True,
    )
    db.add(asset)
    await db.flush()
    db.add(
        LanServiceObservation(
            lan_asset_id=asset.id,
            ip_address=asset.ip_address,
            port=2222,
            protocol="tcp",
            status="open",
            service_name="ssh",
            service_label="possible SSH service",
            confidence=90,
            banner_hint="SSH protocol marker",
            non_standard_ssh=True,
            observed_at=datetime.now(UTC),
            source="authorized_service_check",
        )
    )
    await db.commit()
    await client.post(
        f"/api/v1/monitoring/lan/assets/{asset.id}/posture/assess",
        headers=admin_headers,
    )
    listing = await client.get(
        "/api/v1/monitoring/recommendations",
        headers=admin_headers,
        params={"asset_id": str(asset.id)},
    )
    ssh_item = next(
        item
        for item in listing.json()["items"]
        if item["title"] == "Review SSH on non-standard port"
    )
    patched = await client.patch(
        f"/api/v1/monitoring/recommendations/{ssh_item['id']}",
        headers=admin_headers,
        json={"severity": "high", "notes": "Review accepted by owner."},
    )
    acknowledged = await client.post(
        f"/api/v1/monitoring/recommendations/{ssh_item['id']}/acknowledge",
        headers=admin_headers,
        json={"notes": "Owner review scheduled."},
    )
    resolved = await client.post(
        f"/api/v1/monitoring/recommendations/{ssh_item['id']}/resolve",
        headers=admin_headers,
        json={"notes": "Exposure manually restricted."},
    )
    repeated = await client.post(
        f"/api/v1/monitoring/recommendations/{ssh_item['id']}/resolve",
        headers=admin_headers,
        json={},
    )

    assert patched.status_code == 200
    assert patched.json()["severity"] == "high"
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert repeated.status_code == 409


async def test_posture_endpoints_enforce_rbac(
    client: AsyncClient,
    admin_headers: dict[str, str],
    analyst_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    asset = LanAsset(
        ip_address="192.168.0.213",
        status="online",
        source="static",
        is_authorized=True,
    )
    db.add(asset)
    await db.commit()

    unauthenticated = await client.get("/api/v1/monitoring/posture/overview")
    analyst = await client.post(
        f"/api/v1/monitoring/lan/assets/{asset.id}/posture/assess",
        headers=analyst_headers,
    )
    admin = await client.post(
        f"/api/v1/monitoring/lan/assets/{asset.id}/posture/assess",
        headers=admin_headers,
    )

    assert unauthenticated.status_code in {401, 403}
    assert analyst.status_code == 403
    assert admin.status_code == 200


async def test_report_includes_safe_matching_endpoint_posture(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    asset = LanAsset(
        ip_address="192.168.0.214",
        hostname="report-endpoint",
        status="online",
        source="agent",
        is_authorized=True,
    )
    db.add(asset)
    await db.flush()
    db.add_all(
        [
            Target(
                investigation_id=test_investigation.id,
                target_type="ip",
                target_value=asset.ip_address,
                created_by=test_investigation.owner_id,
            ),
            EndpointSecurityPosture(
                lan_asset_id=asset.id,
                posture_score=60,
                posture_status="at_risk",
                firewall_status="disabled",
                antivirus_status="enabled",
                patch_status="stale",
                pending_reboot=False,
                os_name="Test OS",
                os_version="1",
                disk_health="healthy",
                agent_freshness="fresh",
                risky_services_count=0,
                recommendation_count=1,
                assessed_at=datetime.now(UTC),
                event_metadata={"evidence_mode": "agent_and_stored_observations"},
            ),
            EndpointRemediationRecommendation(
                lan_asset_id=asset.id,
                dedupe_key=f"endpoint-posture:{asset.id}:firewall_disabled",
                title="Enable endpoint firewall",
                severity="high",
                reason="Firewall disabled risk indicator.",
                recommended_action="Enable the approved firewall policy manually.",
                manual_steps=["Confirm locally.", "Apply approved policy."],
                isolation_recommended=False,
                evidence_source="endpoint_agent",
                confidence="high",
            ),
        ]
    )
    await db.commit()

    created = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=analyst_headers,
        json={"report_type": "executive"},
    )

    assert created.status_code == 200
    detail = await client.get(
        f"/api/v1/reports/{created.json()['id']}", headers=analyst_headers
    )
    assert detail.status_code == 200
    assert "Endpoint posture (advisory)" in detail.json()["markdown_content"]
    assert "No exploit validation was performed" in detail.json()["html_content"]
    pdf = await client.get(
        f"/api/v1/reports/{created.json()['id']}/download",
        headers=analyst_headers,
        params={"format": "pdf"},
    )
    docx = await client.get(
        f"/api/v1/reports/{created.json()['id']}/download",
        headers=analyst_headers,
        params={"format": "docx"},
    )
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert docx.status_code == 200
    assert docx.content.startswith(b"PK")
