from __future__ import annotations

from app.services.knowledge.document_loader import load_documents_from_paths


def test_load_documents_recurses_supported_files_and_ignores_noise(tmp_path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Note\n", encoding="utf-8")
    nested = root / "playbooks"
    nested.mkdir()
    (nested / "checklist.txt").write_text("Checklist\n", encoding="utf-8")
    ignored = root / ".git"
    ignored.mkdir()
    (ignored / "secret.md").write_text("# Ignore\n", encoding="utf-8")
    (root / "image.png").write_bytes(b"\x89PNG")

    documents = load_documents_from_paths([root], source_type="security_notes")

    assert [document.path.name for document in documents] == [
        "checklist.txt",
        "note.md",
    ]
    assert all(document.source_type == "security_notes" for document in documents)
