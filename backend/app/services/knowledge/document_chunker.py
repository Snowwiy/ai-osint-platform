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
    max_chars = max(100, max_chars)
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
    max_chars = max(100, max_chars)
    if len(section_text) <= max_chars:
        return [section_text]
    heading_context = _with_heading_context(heading_path, "")
    if len(heading_context) > max_chars // 2:
        heading_context = heading_context[: max_chars // 2]
    paragraphs = _paragraphs_preserving_fences(section_text)
    chunks: list[str] = []
    current = heading_context
    for paragraph in paragraphs:
        if paragraph == heading_context or paragraph in heading_context.splitlines():
            continue
        available = max(1, max_chars - len(heading_context) - 2)
        for fragment in _split_large_paragraph(paragraph, available):
            candidate = f"{current}\n\n{fragment}".strip()
            if len(candidate) > max_chars and current.strip() != heading_context:
                chunks.append(current.strip())
                current = f"{heading_context}\n\n{fragment}".strip()
            else:
                current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _split_large_paragraph(paragraph: str, limit: int) -> list[str]:
    if len(paragraph) <= limit:
        return [paragraph]
    lines = paragraph.splitlines()
    stripped = lines[0].lstrip() if lines else ""
    fence = stripped[:3] if stripped.startswith(("```", "~~~")) else None
    if fence:
        opening = lines[0]
        closing = next(
            (line for line in reversed(lines[1:]) if line.lstrip().startswith(fence)),
            fence,
        )
        body_lines = (
            lines[1:-1]
            if len(lines) > 1 and lines[-1].lstrip().startswith(fence)
            else lines[1:]
        )
        wrapper_size = len(opening) + len(closing) + 2
        body_limit = max(1, limit - wrapper_size)
        body_segments = _split_lines(body_lines, body_limit)
        return [f"{opening}\n{body}\n{closing}" for body in body_segments]
    return _split_text(paragraph, limit)


def _split_lines(lines: list[str], limit: int) -> list[str]:
    segments: list[str] = []
    current = ""
    for line in lines:
        pieces = _split_text(line, limit)
        for piece in pieces:
            candidate = f"{current}\n{piece}".strip()
            if len(candidate) > limit and current:
                segments.append(current)
                current = piece
            else:
                current = candidate
    if current:
        segments.append(current)
    return segments or [""]


def _split_text(content: str, limit: int) -> list[str]:
    words = content.split()
    segments: list[str] = []
    current = ""
    for word in words:
        word_parts = [
            word[index : index + limit] for index in range(0, len(word), limit)
        ]
        for part in word_parts:
            candidate = f"{current} {part}".strip()
            if len(candidate) > limit and current:
                segments.append(current)
                current = part
            else:
                current = candidate
    if current:
        segments.append(current)
    return segments or [content[:limit]]


def _paragraphs_preserving_fences(content: str) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    fence: str | None = None
    for line in content.splitlines():
        stripped = line.lstrip()
        marker = stripped[:3] if stripped.startswith(("```", "~~~")) else None
        if marker:
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
        if not line.strip() and fence is None:
            paragraph = "\n".join(current).strip()
            if paragraph:
                paragraphs.append(paragraph)
            current = []
            continue
        current.append(line)
    paragraph = "\n".join(current).strip()
    if paragraph:
        paragraphs.append(paragraph)
    return paragraphs
