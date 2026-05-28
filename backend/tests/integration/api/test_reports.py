from __future__ import annotations

from app.core.config import settings
from app.core.security import create_access_token
from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.recon_entity import ReconEntity
from app.models.report import Report
from app.models.threat_finding import ThreatFinding
from app.schemas.report import ReportDetailResponse, ReportResponse
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def test_create_report_renders_html_markdown_and_preserves_citations(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    await _add_report_data(db, test_investigation.id)

    response = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=analyst_headers,
        json={"report_type": "technical"},
    )

    assert response.status_code == 200
    parsed = ReportResponse.model_validate(response.json())
    assert parsed.status == "ready"
    assert parsed.report_type == "technical"
    assert parsed.report_metadata["finding_count"] == 1

    report = await db.get(Report, parsed.id)
    assert report is not None
    assert report.html_content is not None
    assert "<h2>Executive Summary</h2>" in report.html_content
    assert "Knowledge Citations" in report.html_content
    assert report.markdown_content is not None
    assert "## Key Findings" in report.markdown_content
    assert "knowledge:" in report.markdown_content


async def test_list_and_get_report_require_membership(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
    other_user,
) -> None:
    created = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=analyst_headers,
        json={"report_type": "executive", "title": "Executive Brief"},
    )
    assert created.status_code == 200
    report_id = created.json()["id"]
    other_token = create_access_token(user_id=str(other_user.id), role=other_user.role)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    list_response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=other_headers,
    )
    get_response = await client.get(
        f"/api/v1/reports/{report_id}",
        headers=other_headers,
    )
    download_response = await client.get(
        f"/api/v1/reports/{report_id}/download",
        headers=other_headers,
        params={"format": "pdf"},
    )

    assert list_response.status_code == 404
    assert get_response.status_code == 404
    assert download_response.status_code == 404
    reports = (await db.execute(select(Report))).scalars().all()
    assert len(reports) == 1


async def test_admin_can_access_reports(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_headers: dict[str, str],
    test_investigation,
) -> None:
    created = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=analyst_headers,
        json={"report_type": "technical"},
    )
    report_id = created.json()["id"]

    response = await client.get(
        f"/api/v1/reports/{report_id}",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert ReportDetailResponse.model_validate(response.json()).id


async def test_empty_investigation_report_has_fallback_sections(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=analyst_headers,
        json={"report_type": "executive"},
    )

    assert response.status_code == 200
    detail = await client.get(
        f"/api/v1/reports/{response.json()['id']}",
        headers=analyst_headers,
    )
    body = detail.json()
    assert "No stored AI analysis" in body["markdown_content"]
    assert "No correlation findings" in body["html_content"]


async def test_report_download_formats(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    created = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=analyst_headers,
        json={"report_type": "technical"},
    )
    report_id = created.json()["id"]

    html = await client.get(
        f"/api/v1/reports/{report_id}/download",
        headers=analyst_headers,
        params={"format": "html"},
    )
    markdown = await client.get(
        f"/api/v1/reports/{report_id}/download",
        headers=analyst_headers,
        params={"format": "md"},
    )
    pdf = await client.get(
        f"/api/v1/reports/{report_id}/download",
        headers=analyst_headers,
        params={"format": "pdf"},
    )
    docx = await client.get(
        f"/api/v1/reports/{report_id}/download",
        headers=analyst_headers,
        params={"format": "docx"},
    )
    invalid = await client.get(
        f"/api/v1/reports/{report_id}/download",
        headers=analyst_headers,
        params={"format": "xlsx"},
    )

    assert html.status_code == 200
    assert "text/html" in html.headers["content-type"]
    assert "<html" in html.text
    assert markdown.status_code == 200
    assert "text/markdown" in markdown.headers["content-type"]
    assert markdown.text.startswith("#")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert docx.status_code == 200
    assert docx.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert docx.content.startswith(b"PK")
    assert invalid.status_code == 422


async def test_report_download_missing_logo_fallback(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(settings, "REPORT_LOGO_PATH", str(tmp_path / "missing.png"))
    created = await client.post(
        f"/api/v1/investigations/{test_investigation.id}/reports",
        headers=analyst_headers,
        json={"report_type": "executive"},
    )
    report_id = created.json()["id"]

    response = await client.get(
        f"/api/v1/reports/{report_id}/download",
        headers=analyst_headers,
        params={"format": "pdf"},
    )

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


async def _add_report_data(db: AsyncSession, investigation_id) -> None:
    entity = ReconEntity(
        investigation_id=investigation_id,
        entity_type="Domain",
        value="example.com",
        display_name="example.com",
        properties={"server": "Apache/2.4.49"},
        source="http",
    )
    db.add(entity)
    await db.flush()
    finding = Finding(
        investigation_id=investigation_id,
        title="Risky server disclosure for example.com",
        description="The HTTP Server header discloses technology details.",
        severity="low",
        confidence_score=70,
        risk_score=20,
        source="http",
        raw_data={},
        normalized_data={},
        status="open",
        created_by=None,
    )
    db.add(finding)
    await db.flush()
    db.add(
        FindingEvidence(
            finding_id=finding.id,
            recon_entity_id=entity.id,
            threat_finding_id=None,
            evidence_type="http_header",
            source="http",
            description="Server header exposes Apache/2.4.49.",
            data={"server": "Apache/2.4.49"},
        )
    )
    db.add(
        ThreatFinding(
            investigation_id=investigation_id,
            recon_entity_id=entity.id,
            target_type="domain",
            target_value="example.com",
            provider="virustotal",
            status="completed",
            risk_score=20,
            confidence="low",
            verdict="low",
            signals=["malicious:0"],
            normalized_data={"malicious": 0},
            raw_data={},
        )
    )
    await db.commit()
