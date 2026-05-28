from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z0-9][A-Za-z0-9_-]*)")
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


@dataclass(frozen=True)
class ParsedMarkdown:
    title: str
    headings: list[str]
    tags: list[str]
    wikilinks: list[str]


def parse_markdown(content: str) -> ParsedMarkdown:
    frontmatter, body = _split_frontmatter(content)
    headings = [match.group(2).strip() for match in _HEADING_RE.finditer(body)]
    title = headings[0] if headings else _first_nonempty_line(body)
    tags = sorted({*_frontmatter_tags(frontmatter), *_inline_tags(body)})
    wikilinks = sorted({link.strip() for link in _WIKILINK_RE.findall(body)})
    return ParsedMarkdown(
        title=title or "Untitled",
        headings=headings,
        tags=tags,
        wikilinks=wikilinks,
    )


def _split_frontmatter(content: str) -> tuple[str, str]:
    if not content.startswith("---"):
        return "", content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return "", content
    return parts[1], parts[2]


def _frontmatter_tags(frontmatter: str) -> list[str]:
    tags: list[str] = []
    in_tags = False
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("tags:"):
            in_tags = True
            inline = stripped.removeprefix("tags:").strip()
            if inline:
                tags.extend(_clean_tag(item) for item in inline.strip("[]").split(","))
            continue
        if in_tags and stripped.startswith("-"):
            tags.append(_clean_tag(stripped.removeprefix("-")))
            continue
        if in_tags and stripped and not line.startswith((" ", "\t")):
            in_tags = False
    return [tag for tag in tags if tag]


def _inline_tags(content: str) -> list[str]:
    return [_clean_tag(match) for match in _TAG_RE.findall(content)]


def _clean_tag(value: str) -> str:
    return value.strip().strip('"').strip("'").removeprefix("#").lower()


def _first_nonempty_line(content: str) -> str:
    for line in content.splitlines():
        clean = line.strip().lstrip("#").strip()
        if clean:
            return clean
    return ""
