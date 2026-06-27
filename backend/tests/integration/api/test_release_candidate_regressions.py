from __future__ import annotations

from app.models.finding import Finding
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import VALID_AUTH_STATEMENT


async def test_login_wrong_password_returns_clean_401(
    client: AsyncClient,
    analyst_user,
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": analyst_user.email, "password": "WrongPassword999!"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


async def test_protected_route_rejects_anonymous_user(client: AsyncClient) -> None:
    response = await client.get("/api/v1/review-board")

    assert response.status_code == 401


async def test_archive_restore_and_purge_governance(
    client: AsyncClient,
    analyst_headers: dict[str, str],
) -> None:
    created = await _create_investigation(client, analyst_headers, "Purge RC")
    investigation_id = created["id"]

    active_purge = await client.delete(
        f"/api/v1/investigations/{investigation_id}/purge",
        headers=analyst_headers,
    )
    assert active_purge.status_code == 409

    archived = await client.delete(
        f"/api/v1/investigations/{investigation_id}",
        headers=analyst_headers,
    )
    assert archived.status_code == 204

    restored = await client.patch(
        f"/api/v1/investigations/{investigation_id}/state",
        headers=analyst_headers,
        json={"status": "active", "reason": "Release candidate restore check"},
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"

    await client.delete(
        f"/api/v1/investigations/{investigation_id}",
        headers=analyst_headers,
    )
    impact = await client.get(
        f"/api/v1/investigations/{investigation_id}/purge-impact",
        headers=analyst_headers,
    )
    assert impact.status_code == 200
    assert impact.json()["permanent_deletion_enabled"] is True

    purged = await client.delete(
        f"/api/v1/investigations/{investigation_id}/purge",
        headers=analyst_headers,
    )
    assert purged.status_code == 204

    missing = await client.get(
        f"/api/v1/investigations/{investigation_id}",
        headers=analyst_headers,
    )
    assert missing.status_code == 404


async def test_member_lookup_and_duplicate_errors_are_stable(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_user,
    other_user,
) -> None:
    created = await _create_investigation(client, analyst_headers, "Members RC")
    investigation_id = created["id"]

    by_username = await client.post(
        f"/api/v1/investigations/{investigation_id}/members",
        headers=analyst_headers,
        json={"username": admin_user.username, "role": "viewer"},
    )
    assert by_username.status_code == 201
    assert by_username.json()["role"] == "viewer"

    by_email = await client.post(
        f"/api/v1/investigations/{investigation_id}/members",
        headers=analyst_headers,
        json={"email": other_user.email, "role": "collaborator"},
    )
    assert by_email.status_code == 201
    assert by_email.json()["role"] == "collaborator"

    duplicate = await client.post(
        f"/api/v1/investigations/{investigation_id}/members",
        headers=analyst_headers,
        json={"username": admin_user.username, "role": "viewer"},
    )
    assert duplicate.status_code == 409

    missing_user = await client.post(
        f"/api/v1/investigations/{investigation_id}/members",
        headers=analyst_headers,
        json={"email": "missing@example.test", "role": "viewer"},
    )
    assert missing_user.status_code == 404


async def test_case_review_report_approval_and_remediation_validation(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    completeness = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/completeness",
        headers=analyst_headers,
    )
    assert completeness.status_code == 200
    assert 0 <= completeness.json()["score"] <= 100

    submitted = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/review/submit",
        headers=analyst_headers,
        json={"notes": "Ready for release candidate review."},
    )
    assert submitted.status_code == 200
    assert submitted.json()["review_status"] == "pending_review"

    approved = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/review/decision",
        headers=analyst_headers,
        json={"decision": "approve", "notes": "Review approved."},
    )
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"

    report = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=analyst_headers,
        json={"report_type": "executive", "title": "RC Executive Report"},
    )
    assert report.status_code == 200
    report_id = report.json()["id"]

    report_submitted = await client.post(
        f"/api/v1/reports/{report_id}/submit-approval",
        headers=analyst_headers,
        json={"notes": "Report ready for approval."},
    )
    assert report_submitted.status_code == 200
    assert report_submitted.json()["approval_status"] == "pending_approval"

    report_approved = await client.post(
        f"/api/v1/reports/{report_id}/approval-decision",
        headers=analyst_headers,
        json={"decision": "approve", "notes": "Report approved."},
    )
    assert report_approved.status_code == 200
    assert report_approved.json()["approval_status"] == "approved"

    finding = Finding(
        investigation_id=test_investigation.id,
        title="Release candidate remediation finding",
        description="A deterministic finding used to verify validation workflow.",
        severity="medium",
        confidence_score=75,
        risk_score=45,
        source="test",
        raw_data={},
        normalized_data={},
        status="open",
        created_by=None,
    )
    db.add(finding)
    await db.commit()
    await db.refresh(finding)

    validation_submitted = await client.post(
        f"/api/v1/findings/{finding.id}/validation/submit",
        headers=analyst_headers,
        json={"validation_notes": "Remediation evidence is ready."},
    )
    assert validation_submitted.status_code == 200
    assert validation_submitted.json()["validation_status"] == "validation_pending"

    validation_approved = await client.post(
        f"/api/v1/findings/{finding.id}/validation/decision",
        headers=analyst_headers,
        json={"decision": "validate", "notes": "Validation approved."},
    )
    assert validation_approved.status_code == 200
    assert validation_approved.json()["validation_status"] == "validated"

    review_board = await client.get(
        "/api/v1/review-board",
        headers=analyst_headers,
        params={"status": "approved"},
    )
    assert review_board.status_code == 200

    closed = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/close",
        headers=analyst_headers,
        json={"closure_reason": "Release candidate closure verified."},
    )
    assert closed.status_code == 200
    assert closed.json()["review_status"] == "closed"


async def test_case_closure_override_requires_reason(
    client: AsyncClient,
    analyst_headers: dict[str, str],
) -> None:
    created = await _create_investigation(client, analyst_headers, "Close Guard RC")
    investigation_id = created["id"]

    blocked = await client.post(
        f"/api/v1/investigations/{investigation_id}/close",
        headers=analyst_headers,
        json={"closure_reason": "Attempt closure before approval."},
    )

    assert blocked.status_code == 409


async def _create_investigation(
    client: AsyncClient,
    headers: dict[str, str],
    title: str,
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/investigations/",
        headers=headers,
        json={
            "title": title,
            "description": "Release candidate regression coverage",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
    )
    assert response.status_code == 201
    return response.json()
