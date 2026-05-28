from __future__ import annotations

from app.services.knowledge.markdown_parser import parse_markdown


def test_parse_markdown_extracts_title_headings_tags_and_wikilinks() -> None:
    parsed = parse_markdown(
        """---
tags:
  - osint
  - playbook
---
# DNS Recon Playbook

Use [[Passive DNS]] and #dns notes.

## SPF Checks

Look for #email-security and [[DMARC]].
"""
    )

    assert parsed.title == "DNS Recon Playbook"
    assert parsed.headings == ["DNS Recon Playbook", "SPF Checks"]
    assert parsed.tags == ["dns", "email-security", "osint", "playbook"]
    assert parsed.wikilinks == ["DMARC", "Passive DNS"]


def test_parse_markdown_uses_first_nonempty_line_for_txt_notes() -> None:
    parsed = parse_markdown("\nIncident response checklist\n\n- contain\n")

    assert parsed.title == "Incident response checklist"
    assert parsed.headings == []
    assert parsed.tags == []
