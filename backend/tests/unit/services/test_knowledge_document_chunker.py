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
