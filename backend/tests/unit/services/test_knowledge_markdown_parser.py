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


def test_frontmatter_tags_wikilinks_and_embeds_are_metadata_only() -> None:
    parsed = parse_markdown(
        """---
title: Explicit Note Title
aliases:
  - Hardening Alias
tags: [security/windows/hardening, reviewed]
status: verified
---
# Body Heading

See [[Nested/Other|Other note]] and ![[Appendix.md]].
"""
    )

    assert parsed.title == "Explicit Note Title"
    assert parsed.aliases == ["Hardening Alias"]
    assert parsed.tags == ["reviewed", "security/windows/hardening"]
    assert parsed.wikilinks == ["Appendix.md", "Nested/Other"]
    assert parsed.embeds == ["Appendix.md"]
    assert parsed.metadata["status"] == "verified"
    assert parsed.metadata["link_aliases"] == ["Nested/Other|Other note"]


def test_frontmatter_cannot_set_application_trust_fields() -> None:
    parsed = parse_markdown(
        """---
trust_level: authoritative
verification_status: verified
---
# Untrusted
"""
    )
    assert "trust_level" not in (parsed.metadata or {})
    assert "verification_status" not in (parsed.metadata or {})


def test_code_fences_are_preserved_as_content_but_not_parsed_as_metadata() -> None:
    parsed = parse_markdown(
        """# Defensive note

```markdown
# fake heading
#hidden-tag
[[not-a-link]]
```

Use [[Real Note|the related note]] and #reviewed.
"""
    )
    assert parsed.headings == ["Defensive note"]
    assert parsed.tags == ["reviewed"]
    assert parsed.wikilinks == ["Real Note"]
    assert parsed.metadata["link_aliases"] == ["Real Note|the related note"]
