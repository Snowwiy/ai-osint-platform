from __future__ import annotations

from app.services.knowledge.document_chunker import chunk_document


def test_chunk_document_preserves_heading_context() -> None:
    chunks = chunk_document(
        """# OSINT Collection

Context for the whole playbook.

## DNS

Use passive DNS only.

## Certificates

Review crt.sh history.
""",
        max_chars=120,
    )

    assert len(chunks) == 3
    assert chunks[0].heading_path == ["OSINT Collection"]
    assert chunks[1].heading_path == ["OSINT Collection", "DNS"]
    assert chunks[1].content.startswith("# OSINT Collection\n## DNS")
    assert "Use passive DNS only." in chunks[1].content


def test_chunk_document_splits_large_sections_on_paragraphs() -> None:
    chunks = chunk_document(
        "# Long Note\n\n"
        "First paragraph with context.\n\n"
        "Second paragraph with more operational detail.\n\n"
        "Third paragraph with final notes.",
        max_chars=80,
    )

    assert len(chunks) >= 2
    assert all(chunk.content.startswith("# Long Note") for chunk in chunks)


def test_chunk_document_keeps_fenced_code_blocks_with_blank_lines_intact() -> None:
    chunks = chunk_document(
        "# Safe example\n\nIntro text.\n\n"
        "```text\nline one\n\nline two\n```\n\nConclusion.",
        max_chars=120,
    )
    code_chunks = [chunk.content for chunk in chunks if "```text" in chunk.content]
    assert len(code_chunks) == 1
    assert "line one\n\nline two\n```" in code_chunks[0]


def test_chunk_document_splits_large_code_at_safe_boundaries() -> None:
    code = "\n".join(
        f"line_{index} = 'bounded illustrative text'" for index in range(30)
    )
    chunks = chunk_document(
        "# Boundaries\n\n"
        + ("An oversized explanatory paragraph remains searchable. " * 8)
        + "\n\n```python\n"
        + code
        + "\n```",
        max_chars=120,
    )

    assert len(chunks) > 2
    assert all(len(chunk.content) <= 120 for chunk in chunks)
    code_chunks = [chunk.content for chunk in chunks if "```python" in chunk.content]
    assert len(code_chunks) > 1
    assert all(
        chunk.count("```python") == 1 and chunk.rstrip().endswith("```")
        for chunk in code_chunks
    )
