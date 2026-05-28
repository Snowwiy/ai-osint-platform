from __future__ import annotations

import html
import io
import re
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from app.core.config import settings
from app.models.report import Report
from app.schemas.report import ReportDownloadFormat


PDF_MEDIA_TYPE = "application/pdf"
DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@dataclass(frozen=True)
class ReportBranding:
    company_name: str
    logo_path: Path | None
    primary_color: str
    secondary_color: str


@dataclass(frozen=True)
class ReportExport:
    content: bytes
    media_type: str
    extension: str


def export_report(report: Report, export_format: ReportDownloadFormat) -> ReportExport:
    if export_format == "html":
        return ReportExport(
            content=(report.html_content or _fallback_html(report)).encode("utf-8"),
            media_type="text/html; charset=utf-8",
            extension="html",
        )
    if export_format == "md":
        return ReportExport(
            content=_markdown_content(report).encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            extension="md",
        )
    branding = get_report_branding()
    if export_format == "pdf":
        return ReportExport(
            content=_export_pdf(report, branding),
            media_type=PDF_MEDIA_TYPE,
            extension="pdf",
        )
    return ReportExport(
        content=_export_docx(report, branding),
        media_type=DOCX_MEDIA_TYPE,
        extension="docx",
    )


def get_report_branding() -> ReportBranding:
    logo_path = _optional_existing_path(settings.REPORT_LOGO_PATH)
    return ReportBranding(
        company_name=_clean_text(settings.REPORT_COMPANY_NAME) or "RavenTech",
        logo_path=logo_path,
        primary_color=_safe_hex(settings.REPORT_PRIMARY_COLOR, "#7C3AED"),
        secondary_color=_safe_hex(settings.REPORT_SECONDARY_COLOR, "#111827"),
    )


def _export_pdf(report: Report, branding: ReportBranding) -> bytes:
    colors = cast(Any, import_module("reportlab.lib.colors"))
    pagesizes = cast(Any, import_module("reportlab.lib.pagesizes"))
    styles_module = cast(Any, import_module("reportlab.lib.styles"))
    units = cast(Any, import_module("reportlab.lib.units"))
    platypus = cast(Any, import_module("reportlab.platypus"))

    primary = colors.HexColor(branding.primary_color)
    secondary = colors.HexColor(branding.secondary_color)
    light_fill = colors.HexColor("#F3F4F6")
    buffer = io.BytesIO()
    doc = platypus.SimpleDocTemplate(
        buffer,
        pagesize=pagesizes.LETTER,
        rightMargin=54,
        leftMargin=54,
        topMargin=64,
        bottomMargin=54,
        title=_report_title(report),
    )
    styles = styles_module.getSampleStyleSheet()
    styles.add(
        styles_module.ParagraphStyle(
            name="RavenTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=secondary,
            spaceAfter=14,
        )
    )
    styles.add(
        styles_module.ParagraphStyle(
            name="RavenHeading",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=primary,
            spaceBefore=12,
            spaceAfter=8,
        )
    )
    styles.add(
        styles_module.ParagraphStyle(
            name="RavenSubheading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=secondary,
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    styles.add(
        styles_module.ParagraphStyle(
            name="RavenBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            spaceAfter=5,
        )
    )
    styles.add(
        styles_module.ParagraphStyle(
            name="RavenCode",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=8,
            leading=10,
            backColor=light_fill,
            leftIndent=6,
            rightIndent=6,
            spaceBefore=4,
            spaceAfter=6,
        )
    )
    styles.add(
        styles_module.ParagraphStyle(
            name="RavenTableCell",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
        )
    )

    story: list[Any] = []
    _add_pdf_cover(report, branding, story, styles, platypus, units, colors)
    story.append(platypus.PageBreak())
    _add_pdf_toc(report, story, styles, platypus)
    story.append(platypus.PageBreak())
    _add_pdf_markdown(report, story, styles, platypus, colors)

    def draw_footer(canvas: Any, doc_obj: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(primary)
        canvas.setFillColor(secondary)
        canvas.setFont("Helvetica", 8)
        canvas.line(doc.leftMargin, 40, doc.pagesize[0] - doc.rightMargin, 40)
        canvas.drawString(doc.leftMargin, 28, branding.company_name)
        canvas.drawRightString(
            doc.pagesize[0] - doc.rightMargin,
            28,
            f"Page {doc_obj.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return buffer.getvalue()


def _export_docx(report: Report, branding: ReportBranding) -> bytes:
    docx_module = cast(Any, import_module("docx"))
    shared = cast(Any, import_module("docx.shared"))
    document = docx_module.Document()

    styles = document.styles
    styles["Normal"].font.name = "Arial"

    title = _report_title(report)
    document.add_heading(branding.company_name, level=0)
    if branding.logo_path is None:
        document.add_paragraph("RavenTech branding placeholder")
    else:
        try:
            document.add_picture(str(branding.logo_path), width=shared.Inches(1.25))
        except Exception:
            document.add_paragraph("RavenTech branding placeholder")
    document.add_heading(title, level=1)
    document.add_paragraph(f"Report type: {_clean_text(report.report_type).title()}")
    document.add_paragraph(f"Risk level: {_risk_level(report).upper()}")

    _add_docx_risk_table(document, report)
    document.add_page_break()
    _add_docx_toc(document, report)
    document.add_page_break()
    _add_docx_markdown(document, report)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _add_pdf_cover(
    report: Report,
    branding: ReportBranding,
    story: list[Any],
    styles: Any,
    platypus: Any,
    units: Any,
    colors: Any,
) -> None:
    if branding.logo_path is not None:
        try:
            story.append(
                platypus.Image(
                    str(branding.logo_path),
                    width=1.1 * units.inch,
                    height=1.1 * units.inch,
                )
            )
        except Exception:
            story.append(
                platypus.Paragraph(
                    html.escape("RavenTech branding placeholder"),
                    styles["RavenBody"],
                )
            )
    else:
        story.append(
            platypus.Paragraph(
                html.escape("RavenTech branding placeholder"),
                styles["RavenBody"],
            )
        )
    story.append(platypus.Spacer(1, 16))
    story.append(
        platypus.Paragraph(html.escape(branding.company_name), styles["RavenHeading"])
    )
    story.append(platypus.Paragraph(html.escape(_report_title(report)), styles["RavenTitle"]))
    story.append(
        platypus.Paragraph(
            html.escape(f"{_clean_text(report.report_type).title()} report"),
            styles["RavenBody"],
        )
    )
    story.append(platypus.Spacer(1, 14))
    risk_data = [
        ["Risk Level", "Risk Score", "Findings"],
        [_risk_level(report).upper(), str(_highest_score(report)), str(_finding_count(report))],
    ]
    table = platypus.Table(risk_data, hAlign="LEFT")
    table.setStyle(
        platypus.TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F3F4F6")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(table)


def _add_pdf_toc(
    report: Report,
    story: list[Any],
    styles: Any,
    platypus: Any,
) -> None:
    story.append(platypus.Paragraph("Table of Contents", styles["RavenHeading"]))
    for index, heading in enumerate(_section_headings(report), start=1):
        story.append(
            platypus.Paragraph(
                html.escape(f"{index}. {heading}"),
                styles["RavenBody"],
            )
        )


def _add_pdf_markdown(
    report: Report,
    story: list[Any],
    styles: Any,
    platypus: Any,
    colors: Any,
) -> None:
    lines = _markdown_content(report).splitlines()
    index = 0
    code_lines: list[str] = []
    in_code = False
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                _append_pdf_code(story, styles, platypus, "\n".join(code_lines))
                code_lines = []
            in_code = not in_code
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        table_data, next_index = _read_markdown_table(lines, index)
        if table_data:
            _append_pdf_table(story, styles, platypus, colors, table_data)
            index = next_index
            continue
        if not stripped:
            story.append(platypus.Spacer(1, 4))
        elif stripped.startswith("# "):
            pass
        elif stripped.startswith("## "):
            story.append(
                platypus.Paragraph(
                    html.escape(stripped.removeprefix("## ").strip()),
                    styles["RavenHeading"],
                )
            )
        elif stripped.startswith("### "):
            story.append(
                platypus.Paragraph(
                    html.escape(stripped.removeprefix("### ").strip()),
                    styles["RavenSubheading"],
                )
            )
        elif stripped.startswith("- "):
            story.append(
                platypus.Paragraph(
                    html.escape(f"- {_inline_text(stripped.removeprefix('- '))}"),
                    styles["RavenBody"],
                )
            )
        else:
            story.append(
                platypus.Paragraph(
                    html.escape(_inline_text(stripped)),
                    styles["RavenBody"],
                )
            )
        index += 1
    if code_lines:
        _append_pdf_code(story, styles, platypus, "\n".join(code_lines))


def _append_pdf_code(
    story: list[Any],
    styles: Any,
    platypus: Any,
    content: str,
) -> None:
    story.append(platypus.Preformatted(_clean_text(content) or " ", styles["RavenCode"]))


def _append_pdf_table(
    story: list[Any],
    styles: Any,
    platypus: Any,
    colors: Any,
    rows: list[list[str]],
) -> None:
    data = [
        [
            platypus.Paragraph(html.escape(_inline_text(cell)), styles["RavenTableCell"])
            for cell in row
        ]
        for row in rows
    ]
    table = platypus.Table(data, hAlign="LEFT", repeatRows=1)
    table.setStyle(
        platypus.TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)


def _add_docx_risk_table(document: Any, report: Report) -> None:
    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    headers = table.rows[0].cells
    headers[0].text = "Risk Level"
    headers[1].text = "Risk Score"
    headers[2].text = "Findings"
    row = table.add_row().cells
    row[0].text = _risk_level(report).upper()
    row[1].text = str(_highest_score(report))
    row[2].text = str(_finding_count(report))


def _add_docx_toc(document: Any, report: Report) -> None:
    document.add_heading("Table of Contents", level=1)
    for heading in _section_headings(report):
        document.add_paragraph(heading, style="List Number")


def _add_docx_markdown(document: Any, report: Report) -> None:
    lines = _markdown_content(report).splitlines()
    index = 0
    code_lines: list[str] = []
    in_code = False
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                paragraph = document.add_paragraph()
                run = paragraph.add_run(_clean_text("\n".join(code_lines)))
                run.font.name = "Courier New"
                code_lines = []
            in_code = not in_code
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        table_data, next_index = _read_markdown_table(lines, index)
        if table_data:
            _append_docx_table(document, table_data)
            index = next_index
            continue
        if not stripped or stripped.startswith("# "):
            pass
        elif stripped.startswith("## "):
            document.add_heading(_inline_text(stripped.removeprefix("## ")), level=1)
        elif stripped.startswith("### "):
            document.add_heading(_inline_text(stripped.removeprefix("### ")), level=2)
        elif stripped.startswith("- "):
            document.add_paragraph(
                _inline_text(stripped.removeprefix("- ")),
                style="List Bullet",
            )
        else:
            document.add_paragraph(_inline_text(stripped))
        index += 1
    if code_lines:
        paragraph = document.add_paragraph()
        run = paragraph.add_run(_clean_text("\n".join(code_lines)))
        run.font.name = "Courier New"


def _append_docx_table(document: Any, rows: list[list[str]]) -> None:
    if not rows:
        return
    table = document.add_table(rows=1, cols=len(rows[0]))
    table.style = "Table Grid"
    for column_index, cell in enumerate(rows[0]):
        table.rows[0].cells[column_index].text = _inline_text(cell)
    for row in rows[1:]:
        cells = table.add_row().cells
        for column_index, cell in enumerate(row[: len(cells)]):
            cells[column_index].text = _inline_text(cell)


def _read_markdown_table(
    lines: list[str],
    start_index: int,
) -> tuple[list[list[str]], int]:
    if start_index + 1 >= len(lines):
        return [], start_index
    header = lines[start_index]
    separator = lines[start_index + 1]
    if "|" not in header or not _is_separator_row(separator):
        return [], start_index
    rows: list[list[str]] = [_parse_table_row(header)]
    index = start_index + 2
    while index < len(lines) and "|" in lines[index] and lines[index].strip():
        rows.append(_parse_table_row(lines[index]))
        index += 1
    width = len(rows[0])
    normalized = [(row + [""] * width)[:width] for row in rows if row]
    return normalized, index


def _parse_table_row(row: str) -> list[str]:
    return [_inline_text(cell.strip()) for cell in row.strip().strip("|").split("|")]


def _is_separator_row(row: str) -> bool:
    stripped = row.strip()
    if "|" not in stripped:
        return False
    cells = stripped.strip("|").split("|")
    return all(re.fullmatch(r"\s*:?-{3,}:?\s*", cell) for cell in cells)


def _section_headings(report: Report) -> list[str]:
    headings = []
    for line in _markdown_content(report).splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            headings.append(_inline_text(stripped.removeprefix("## ").strip()))
    return headings


def _markdown_content(report: Report) -> str:
    markdown = report.markdown_content or ""
    if markdown.strip():
        return _clean_text(markdown)
    html_content = report.html_content or ""
    if html_content.strip():
        plain = re.sub(r"<[^>]+>", " ", html_content)
        markdown = html.unescape(plain)
    if not markdown.strip():
        markdown = (
            f"# {_report_title(report)}\n\n"
            "## Executive Summary\n\n"
            "No report content is currently available.\n\n"
            "## Appendix\n\n"
            "- No citations or evidence are currently available.\n"
        )
    return _clean_text(markdown).strip() + "\n"


def _fallback_html(report: Report) -> str:
    paragraphs = [
        f"<h1>{html.escape(_report_title(report))}</h1>",
        "<p>No rendered HTML report content is currently available.</p>",
    ]
    return "<!doctype html><html><body>" + "".join(paragraphs) + "</body></html>"


def _report_title(report: Report) -> str:
    return _clean_text(report.title or "Investigation Report")


def _metadata(report: Report) -> dict[str, Any]:
    return dict(report.report_metadata or {})


def _risk_level(report: Report) -> str:
    return _clean_text(_metadata(report).get("risk_level", "not_assessed"))


def _highest_score(report: Report) -> int:
    score = _metadata(report).get("highest_score")
    if isinstance(score, int):
        return score
    return 0


def _finding_count(report: Report) -> int:
    count = _metadata(report).get("finding_count")
    if isinstance(count, int):
        return count
    return 0


def _optional_existing_path(raw_path: str) -> Path | None:
    path_value = raw_path.strip()
    if not path_value:
        return None
    path = Path(path_value)
    if path.is_file():
        return path
    return None


def _safe_hex(value: str, fallback: str) -> str:
    candidate = value.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", candidate):
        return candidate
    return fallback


def _inline_text(value: object) -> str:
    text = _clean_text(value)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    return text.strip()


def _clean_text(value: object) -> str:
    text = str(value)
    text = html.unescape(text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text.strip()
