from __future__ import annotations

from app.core.security import create_access_token
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.schemas.report import ReportDetailResponse
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import VALID_AUTH_STATEMENT


async def test_workflow_transition_validation(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    invalid = await client.put(
        f"/api/v1/investigations/{test_investigation.id}",
        headers=analyst_headers,
        json={"status": "remediated"},
    )
    valid = await client.put(
        f"/api/v1/investigations/{test_investigation.id}",
        headers=analyst_headers,
        json={"status": "review"},
    )

    assert invalid.status_code == 409
    assert "Invalid workflow transition" in invalid.json()["detail"]
    assert valid.status_code == 200
    assert valid.json()["status"] == "review"


async def test_notes_crud_and_sanitization(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    created = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/notes",
        headers=analyst_headers,
        json={
            "title": "Initial analyst summary",
            "note": "# Summary\n<script>alert(1)</script>\n- scoped evidence",
            "note_type": "executive",
        },
    )
    assert created.status_code == 201
    note = created.json()
    assert "<script" not in note["note"]
    assert note["note_type"] == "executive"

    updated = await client.patch(
        f"/api/v1/investigations/{test_investigation.id}/notes/{note['id']}",
        headers=analyst_headers,
        json={"note_type": "remediation", "title": "Remediation summary"},
    )
    listed = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/notes",
        headers=analyst_headers,
    )
    deleted = await client.delete(
        f"/api/v1/investigations/{test_investigation.id}/notes/{note['id']}",
        headers=analyst_headers,
    )

    assert updated.status_code == 200
    assert updated.json()["note_type"] == "remediation"
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert deleted.status_code == 204


async def test_tasks_crud_and_completion(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    created = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/tasks",
        headers=analyst_headers,
        json={
            "title": "Validate exposed service",
            "description": "Confirm whether the evidence is still relevant.",
            "priority": "high",
        },
    )
    task_id = created.json()["id"]
    completed = await client.patch(
        f"/api/v1/investigations/{test_investigation.id}/tasks/{task_id}",
        headers=analyst_headers,
        json={"status": "completed"},
    )
    listed = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/tasks",
        headers=analyst_headers,
    )
    deleted = await client.delete(
        f"/api/v1/investigations/{test_investigation.id}/tasks/{task_id}",
        headers=analyst_headers,
    )

    assert created.status_code == 201
    assert completed.status_code == 200
    assert completed.json()["completed_at"] is not None
    assert listed.status_code == 200
    assert listed.json()["items"][0]["status"] == "completed"
    assert deleted.status_code == 204


async def test_case_management_requires_membership(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    admin_user,
) -> None:
    investigation = Investigation(
        title="Private Case",
        owner_id=admin_user.id,
        authorization_statement=VALID_AUTH_STATEMENT,
        status="active",
    )
    db.add(investigation)
    await db.flush()
    db.add(
        InvestigationMember(
            investigation_id=investigation.id,
            user_id=admin_user.id,
            role="owner",
        )
    )
    await db.commit()

    response = await client.get(
        f"/api/v1/investigations/{investigation.id}/notes",
        headers=analyst_headers,
    )

    assert response.status_code == 404


async def test_evidence_links_to_finding_note_and_task(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    finding = Finding(
        investigation_id=test_investigation.id,
        title="Evidence-backed finding",
        description="Finding for case evidence linkage.",
        severity="medium",
        confidence_score=75,
        risk_score=45,
        source="case",
        raw_data={},
        normalized_data={},
        status="open",
    )
    db.add(finding)
    await db.commit()
    await db.refresh(finding)
    note = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/notes",
        headers=analyst_headers,
        json={
            "title": "Evidence note",
            "note": "Analyst evidence context.",
            "note_type": "evidence",
        },
    )
    task = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/tasks",
        headers=analyst_headers,
        json={"title": "Preserve evidence", "priority": "urgent"},
    )

    created = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/evidence",
        headers=analyst_headers,
        json={
            "title": "Passive evidence record",
            "description": "Metadata only evidence.",
            "evidence_type": "finding",
            "source": "analyst",
            "confidence": 80,
            "tags": ["finding", "finding"],
            "analyst_comment": "Preserved for report.",
            "finding_id": str(finding.id),
            "note_id": note.json()["id"],
            "task_id": task.json()["id"],
        },
    )
    listed = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/evidence",
        headers=analyst_headers,
    )

    assert created.status_code == 201
    assert created.json()["finding_id"] == str(finding.id)
    assert created.json()["tags"] == ["finding"]
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


async def test_timeline_and_report_include_case_management_events(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    note = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/notes",
        headers=analyst_headers,
        json={
            "title": "Executive recommendation",
            "note": "Reduce exposed services and track remediation.",
            "note_type": "recommendation",
        },
    )
    task = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/tasks",
        headers=analyst_headers,
        json={"title": "Complete remediation review", "priority": "high"},
    )
    await client.patch(
        f"/api/v1/investigations/{test_investigation.id}/tasks/{task.json()['id']}",
        headers=analyst_headers,
        json={"status": "completed"},
    )
    await client.post(
        f"/api/v1/investigations/{test_investigation.id}/evidence",
        headers=analyst_headers,
        json={
            "title": "Recommendation evidence",
            "evidence_type": "analyst_note",
            "source": "analyst",
            "confidence": 90,
            "note_id": note.json()["id"],
        },
    )

    timeline = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/timeline",
        headers=analyst_headers,
    )
    report = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=analyst_headers,
        json={"report_type": "technical"},
    )
    detail = await client.get(
        f"/api/v1/reports/{report.json()['id']}",
        headers=analyst_headers,
    )

    assert timeline.status_code == 200
    event_types = {event["event_type"] for event in timeline.json()["events"]}
    assert {"note_added", "task_created", "task_completed", "evidence_linked"} <= (
        event_types
    )
    parsed = ReportDetailResponse.model_validate(detail.json())
    assert parsed.markdown_content is not None
    assert "## Remediation Tracking" in parsed.markdown_content
    assert "Recommendation evidence" in parsed.markdown_content


async def test_admin_can_access_case_management(
    client: AsyncClient,
    admin_user,
    test_investigation,
) -> None:
    token = create_access_token(user_id=str(admin_user.id), role=admin_user.role)
    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
