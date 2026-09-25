from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "srs" / "RavenTech_OSINT_SRS_ES.md"
PDF = ROOT / "docs" / "deliverables" / "RavenTech_OSINT_SRS_v1.0_ES.pdf"
README = ROOT / "README.md"


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    reader = PdfReader(str(PDF))
    pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    ids = re.findall(r"^### ((?:FR|NFR)-[A-Z0-9]+-\d{3})\b", source, re.MULTILINE)
    unique = set(ids)
    duplicates = sorted(value for value in unique if ids.count(value) != 1)
    if duplicates:
        raise AssertionError(f"Duplicate requirement IDs: {duplicates}")
    if not 25 <= len(reader.pages) <= 80:
        raise AssertionError(f"Expected 25-80 pages, got {len(reader.pages)}")
    if len(ids) < 100:
        raise AssertionError(f"Expected at least 100 requirements, found {len(ids)}")
    requirement_records = []
    for line in source.splitlines():
        if line.startswith("Plataforma:") and "Estado:" in line:
            platform, state = line.split("Estado:", 1)
            requirement_records.append(
                (
                    platform.removeprefix("Plataforma:").strip().rstrip("."),
                    state.split(".", 1)[0].strip(),
                )
            )
    if len(requirement_records) != len(ids):
        raise AssertionError(
            f"Requirement detail records ({len(requirement_records)}) "
            f"do not match IDs ({len(ids)})."
        )
    allowed_states = {
        "Implementado",
        "Parcial",
        "Planificado",
        "Limitado por plataforma",
        "Especificado",
    }
    allowed_platforms = {"Windows/Linux", "Windows", "Linux", "Docker"}
    invalid_states = sorted(
        {state for _, state in requirement_records} - allowed_states
    )
    invalid_platforms = sorted(
        {platform for platform, _ in requirement_records} - allowed_platforms
    )
    if invalid_states or invalid_platforms:
        raise AssertionError(
            "Inconsistent status/platform vocabulary: "
            f"{invalid_states}, {invalid_platforms}"
        )

    traceability_start = source.find("## 31. Trazabilidad de requisitos")
    if traceability_start < 0:
        raise AssertionError("Requirements traceability section is missing.")
    next_section = source.find("\n## ", traceability_start + 1)
    traceability = source[
        traceability_start : next_section if next_section >= 0 else None
    ]
    matrix_ids: list[str] = []
    matrix_states: list[str] = []
    for line in traceability.splitlines():
        if not line.startswith("|"):
            continue
        fields = [field.strip() for field in line.strip().strip("|").split("|")]
        if fields and re.fullmatch(r"(?:FR|NFR)-[A-Z0-9]+-\d{3}", fields[0]):
            if len(fields) != 8:
                raise AssertionError(f"Malformed traceability row for {fields[0]}.")
            matrix_ids.append(fields[0])
            matrix_states.append(fields[4])
    duplicate_matrix_ids = sorted(
        identifier for identifier, count in Counter(matrix_ids).items() if count != 1
    )
    if duplicate_matrix_ids:
        raise AssertionError(f"Duplicate traceability rows: {duplicate_matrix_ids}")
    if set(matrix_ids) != unique:
        missing_rows = sorted(unique - set(matrix_ids))
        unknown_rows = sorted(set(matrix_ids) - unique)
        raise AssertionError(
            "Traceability coverage mismatch. "
            f"Missing: {missing_rows}; unknown: {unknown_rows}"
        )
    if set(matrix_states) - allowed_states:
        raise AssertionError(
            "Traceability rows use unsupported statuses: "
            f"{sorted(set(matrix_states) - allowed_states)}"
        )
    missing = sorted(value for value in unique if value not in pdf_text)
    if missing:
        raise AssertionError(f"Requirements absent from PDF: {missing[:10]}")
    required = [
        "RavenTech OSINT",
        "5.0.0-rc6",
        "Contenido",
        "Arquitectura",
        "PostgreSQL",
        "SCRAM-SHA-256",
        "Trazabilidad de requisitos",
        "Windows clean-machine",
        "NOT RUN",
        "Obsidian",
        "FR-AUTH-001",
        "NFR-SEC-001",
        "PDF",
        "DOCX",
        "HTML",
        "Markdown",
        "FR-ANL-001",
        "FR-ANL-015",
        "NFR-ANL-001",
        "NFR-ANL-005",
        "correlación",
        "causalidad",
        "insuficiente",
    ]
    missing_terms = [
        term for term in required if term.casefold() not in pdf_text.casefold()
    ]
    if missing_terms:
        raise AssertionError(f"PDF is missing required terms: {missing_terms}")
    forbidden = [
        "Phase 5BO",
        "Phase 5BN",
        "Fase 5BO",
        "Codex",
        "Claude",
        "DATABASE_URL=",
    ]
    found = [term for term in forbidden if term.casefold() in pdf_text.casefold()]
    if found:
        raise AssertionError(f"Internal history or secret marker found in SRS: {found}")
    source_forbidden = [
        term for term in forbidden if term.casefold() in source.casefold()
    ]
    if source_forbidden:
        raise AssertionError(
            f"Internal history or secret marker found in SRS source: {source_forbidden}"
        )
    if re.search(r"(?i)\b(?:phase|fase)\s*\d+[a-z]?\b", pdf_text):
        raise AssertionError("Internal phase identifier found in the SRS PDF")
    if re.search(r"(?i)\b(?:phase|fase)\s*\d+[a-z]?\b", source):
        raise AssertionError("Internal phase identifier found in the SRS source")
    if re.search(
        r"(?i)(password|api[_ -]?key|access[_ -]?token|jwt[_ -]?secret)\s*[:=]\s*\S+",
        pdf_text,
    ):
        raise AssertionError("Potential secret assignment found in SRS")
    if re.search(r"(?i)[A-Z]:\\Users\\[^\\\s]+", pdf_text):
        raise AssertionError("Private Windows user path found in SRS")
    if re.search(r"(?i)[A-Z]:\\Users\\[^\\\s]+", source):
        raise AssertionError("Private Windows user path found in SRS source")
    numbered_pages = sum(
        "Página" in (page.extract_text() or "") for page in reader.pages
    )
    if numbered_pages < len(reader.pages) - 1:
        raise AssertionError("PDF page numbers are missing from content pages.")
    readme = README.read_text(encoding="utf-8")
    readme_forbidden = [
        r"\b(?:phase|fase)\s*\d+[A-Z]{0,2}\b",
        r"\bCodex\b",
        r"\bClaude\b",
        r"prompt history",
        r"implemented in this phase",
    ]
    violations = [
        pattern
        for pattern in readme_forbidden
        if re.search(pattern, readme, re.IGNORECASE)
    ]
    if violations:
        raise AssertionError(
            f"README contains internal development chronology: {violations}"
        )
    if reader.metadata.title is None or "RavenTech OSINT" not in reader.metadata.title:
        raise AssertionError("PDF title metadata is missing")
    print(
        "SRS validation passed: "
        f"{len(reader.pages)} pages, {len(ids)} unique requirements, "
        f"{PDF.stat().st_size} bytes"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"SRS validation failed: {error}", file=sys.stderr)
        raise
