from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class DocumentChunk:
    content: str
    chunk_index: int
    heading_path: list[str]


def chunk_document(content: str, *, max_chars: int = 1800) -> list[DocumentChunk]:
    sections = _sections_by_heading(content)
    chunks: list[DocumentChunk] = []
    for heading_path, section_body in sections:
        section_text = _with_heading_context(heading_path, section_body)
        for part in _split_section(section_text, heading_path, max_chars=max_chars):
            chunks.append(
                DocumentChunk(
                    content=part,
                    chunk_index=len(chunks),
                    heading_path=heading_path,
                )
            )
    if not chunks and content.strip():
        chunks.append(
            DocumentChunk(content=content.strip(), chunk_index=0, heading_path=[])
        )
    return chunks


def _sections_by_heading(content: str) -> list[tuple[list[str], str]]:
    stack: list[tuple[int, str]] = []
    current_path: list[str] = []
    current_lines: list[str] = []
    sections: list[tuple[list[str], str]] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if current_path or body:
            sections.append((current_path.copy(), body))

    for line in content.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            flush()
            current_lines = []
            level = len(match.group(1))
            title = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current_path = [item[1] for item in stack]
            continue
        current_lines.append(line)
    flush()
    return sections


def _with_heading_context(heading_path: list[str], body: str) -> str:
    heading_lines = [
        f"{'#' * min(index + 1, 6)} {heading}"
        for index, heading in enumerate(heading_path)
    ]
    parts = [*heading_lines, body.strip()]
    return "\n".join(part for part in parts if part).strip()


def _split_section(
    section_text: str,
    heading_path: list[str],
    *,
    max_chars: int,
) -> list[str]:
    if len(section_text) <= max_chars:
        return [section_text]
    heading_context = _with_heading_context(heading_path, "")
    paragraphs = [part.strip() for part in section_text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = heading_context
    for paragraph in paragraphs:
        if paragraph == heading_context or paragraph in heading_context.splitlines():
            continue
        candidate = f"{current}\n\n{paragraph}".strip()
        if len(candidate) > max_chars and current.strip() != heading_context:
            chunks.append(current.strip())
            current = f"{heading_context}\n\n{paragraph}".strip()
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks
