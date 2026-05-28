from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.models.report import Report
from app.services.report_export import DOCX_MEDIA_TYPE, PDF_MEDIA_TYPE, export_report


def test_export_report_generates_pdf() -> None:
    exported = export_report(_report(), "pdf")

    assert exported.media_type == PDF_MEDIA_TYPE
    assert exported.extension == "pdf"
    assert exported.content.startswith(b"%PDF")
    assert len(exported.content) > 1000


def test_export_report_generates_docx() -> None:
    exported = export_report(_report(), "docx")

    assert exported.media_type == DOCX_MEDIA_TYPE
    assert exported.extension == "docx"
    assert exported.content.startswith(b"PK")
    assert len(exported.content) > 1000


def test_export_report_handles_empty_report_content() -> None:
    report = _report(markdown_content="", html_content="")

    pdf = export_report(report, "pdf")
    docx = export_report(report, "docx")

    assert pdf.content.startswith(b"%PDF")
    assert docx.content.startswith(b"PK")


def test_export_report_missing_logo_uses_branding_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(settings, "REPORT_LOGO_PATH", str(tmp_path / "missing.png"))

    exported = export_report(_report(), "pdf")

    assert exported.content.startswith(b"%PDF")


def test_export_report_preserves_existing_html_and_markdown() -> None:
    report = _report()

    html_export = export_report(report, "html")
    markdown_export = export_report(report, "md")

    assert b"knowledge:starter" in html_export.content
    assert b"knowledge:starter" in markdown_export.content


def _report(
    markdown_content: str | None = None,
    html_content: str | None = None,
) -> Report:
    markdown = markdown_content
    if markdown_content is None:
        markdown = (
            "# Executive Brief\n\n"
            "## Executive Summary\n\n"
            "Stored findings indicate limited exposure.\n\n"
            "### Business Impact\n\n"
            "Potential audit and customer trust impact.\n\n"
            "## Key Findings\n\n"
            "- **LOW** Risky server disclosure (risk 20, confidence 70)\n\n"
            "## Technical Evidence\n\n"
            "- http: Server header exposes Apache.\n\n"
            "## Appendix\n\n"
            "- [knowledge:starter] CIS Controls: Secure configuration "
            "(local)\n"
        )
    html_body = html_content
    if html_content is None:
        html_body = (
            "<!doctype html><html><body><h1>Executive Brief</h1>"
            "<p>knowledge:starter</p></body></html>"
        )
    return Report(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        generated_by=uuid.uuid4(),
        title="Executive Brief",
        report_type="technical",
        report_format="html",
        status="ready",
        html_content=html_body,
        markdown_content=markdown,
        file_size_bytes=100,
        report_metadata={
            "finding_count": 1,
            "highest_score": 20,
            "risk_level": "low",
        },
    )
