from __future__ import annotations

from app.models.audit_log import AuditLog
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def test_case_closure_checklist_submit_approve_close_reopen(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
    db: AsyncSession,
) -> None:
    generated = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/closure/generate-checklist",
        headers=analyst_headers,
    )
    assert generated.status_code == 200
    body = generated.json()
    assert body["status"] == "draft"
    assert body["checklist"]

    first_item = body["checklist"][0]
    updated_item = await client.patch(
        f"/api/v1/investigations/{test_investigation.id}/closure/checklist/{first_item['id']}",
        headers=analyst_headers,
        json={"status": "completed", "description": "Reviewed for test."},
    )
    assert updated_item.status_code == 200
    assert updated_item.json()["status"] == "completed"

    submitted = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/closure/submit-review",
        headers=analyst_headers,
        json={"closure_summary": "Ready for client deliverable review."},
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "in_review"

    approved = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/closure/approve",
        headers=analyst_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    blocked_close = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/closure/close",
        headers=analyst_headers,
        json={"closure_summary": "Attempt closure without override."},
    )
    assert blocked_close.status_code == 409

    closed = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/closure/close",
        headers=analyst_headers,
        json={
            "closure_summary": "Client handoff complete with documented warnings.",
            "override_reason": "Test case has intentionally incomplete checklist data.",
        },
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    reopened = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/closure/reopen",
        headers=analyst_headers,
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "reopened"

    actions = (
        await db.execute(
            select(AuditLog.action).where(
                AuditLog.action.in_(
                    [
                        "closure.checklist_generated",
                        "closure.checklist_item_updated",
                        "closure.submitted_for_review",
                        "closure.approved",
                        "closure.closed",
                        "closure.reopened",
                    ]
                )
            )
        )
    ).scalars().all()
    assert "closure.closed" in actions
    assert "closure.reopened" in actions


async def test_case_deliverables_package_and_report_metadata(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
    db: AsyncSession,
) -> None:
    report = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=analyst_headers,
        json={"report_type": "executive", "title": "Closure Executive Report"},
    )
    assert report.status_code == 200
    report_id = report.json()["id"]

    deliverable_payloads = [
        {
            "title": "Executive report",
            "deliverable_type": "executive_report",
            "status": "ready",
            "report_id": report_id,
            "export_format": "pdf",
        },
        {
            "title": "Technical report",
            "deliverable_type": "technical_report",
            "status": "ready",
            "report_id": report_id,
            "export_format": "html",
        },
        {
            "title": "Evidence appendix",
            "deliverable_type": "evidence_appendix",
            "status": "ready",
            "report_id": report_id,
            "export_format": "md",
        },
    ]
    for payload in deliverable_payloads:
        created = await client.post(
            f"/api/v1/investigations/{test_investigation.id}/deliverables",
            headers=analyst_headers,
            json=payload,
        )
        assert created.status_code == 201

    package = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/deliverables/package",
        headers=analyst_headers,
    )
    assert package.status_code == 200
    package_body = package.json()
    assert package_body["included_deliverables"]
    assert package_body["missing_deliverables"] == []
    assert package_body["evidence_package"]["evidence_count"] >= 0

    regenerated = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=analyst_headers,
        json={"report_type": "technical", "title": "Closure Technical Report"},
    )
    assert regenerated.status_code == 200
    detail = await client.get(
        f"/api/v1/reports/{regenerated.json()['id']}",
        headers=analyst_headers,
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["report_metadata"]["closure_workflow_count"] >= 1
    assert "Case Closure and Deliverables" in body["markdown_content"]

    deliverables = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/deliverables",
        headers=analyst_headers,
    )
    assert deliverables.status_code == 200
    assert deliverables.json()["total"] >= 4

    actions = (
        await db.execute(
            select(AuditLog.action).where(
                AuditLog.action.in_(["deliverable.created", "deliverable.packaged"])
            )
        )
    ).scalars().all()
    assert "deliverable.created" in actions
    assert "deliverable.packaged" in actions


async def test_existing_investigation_without_closure_still_reports(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=analyst_headers,
        json={"report_type": "technical"},
    )
    assert response.status_code == 200
    detail = await client.get(
        f"/api/v1/reports/{response.json()['id']}",
        headers=analyst_headers,
    )
    assert detail.status_code == 200
    assert "Case closure workflow has not been prepared" in detail.json()[
        "markdown_content"
    ]
