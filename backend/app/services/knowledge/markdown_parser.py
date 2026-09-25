from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_TAG_RE = re.compile(r"(?<![\w/])#([\w][\w/-]*)", re.UNICODE)
_WIKILINK_RE = re.compile(r"(!?)\[\[([^\]|#]+)(?:\|([^\]]*))?\]\]")


@dataclass(frozen=True)
class ParsedMarkdown:
    title: str
    headings: list[str]
    tags: list[str]
    wikilinks: list[str]
    aliases: list[str] | None = None
    metadata: dict[str, Any] | None = None
    embeds: list[str] | None = None


def parse_markdown(content: str) -> ParsedMarkdown:
    frontmatter, body = _split_frontmatter(content)
    structural_body = _without_fenced_code(body)
    headings = [
        match.group(2).strip() for match in _HEADING_RE.finditer(structural_body)
    ]
    metadata = _safe_frontmatter(frontmatter)
    title_value = metadata.get("title")
    title = (
        str(title_value)
        if title_value
        else headings[0]
        if headings
        else _first_nonempty_line(body)
    )
    tags = sorted({*_frontmatter_tags(frontmatter), *_inline_tags(structural_body)})
    links = [match.groups() for match in _WIKILINK_RE.finditer(structural_body)]
    wikilinks = sorted({target.strip() for _, target, _ in links if target.strip()})
    embeds = sorted(
        {target.strip() for embed, target, _ in links if embed and target.strip()}
    )
    metadata["link_aliases"] = [
        f"{target.strip()}|{alias.strip()}"
        for _, target, alias in links
        if target.strip() and alias and alias.strip()
    ]
    aliases_value = metadata.get("aliases", [])
    aliases = aliases_value if isinstance(aliases_value, list) else [aliases_value]
    return ParsedMarkdown(
        title=title or "Untitled",
        headings=headings,
        tags=tags,
        wikilinks=wikilinks,
        aliases=[item for item in aliases if item],
        metadata=metadata,
        embeds=embeds,
    )


def _without_fenced_code(content: str) -> str:
    lines = content.splitlines(keepends=True)
    output: list[str] = []
    fence: str | None = None
    for line in lines:
        stripped = line.lstrip()
        marker = stripped[:3]
        if fence is None and marker in {"```", "~~~"}:
            fence = marker
            output.append("\n" if line.endswith("\n") else "")
        elif fence is not None:
            if stripped.startswith(fence):
                fence = None
            output.append("\n" if line.endswith("\n") else "")
        else:
            output.append(line)
    return "".join(output)


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
    return value.strip().strip('"').strip("'").removeprefix("#").strip("/").lower()


_SAFE_FRONTMATTER_KEYS = {
    "title",
    "aliases",
    "tags",
    "created",
    "modified",
    "status",
    "category",
    "source",
    "author",
    "references",
    "language",
}


def _safe_frontmatter(frontmatter: str) -> dict[str, Any]:
    """Parse a small, non-executable YAML-like subset; never load YAML objects."""
    result: dict[str, Any] = {}
    key: str | None = None
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in stripped and not stripped.startswith("-"):
            raw_key, raw_value = stripped.split(":", 1)
            normalized = raw_key.strip().lower()
            key = normalized if normalized in _SAFE_FRONTMATTER_KEYS else None
            if key is None:
                continue
            value = raw_value.strip().strip("\\\"'")
            if value.startswith("[") and value.endswith("]"):
                values = [
                    item.strip().strip("\\\"'") for item in value[1:-1].split(",")
                ]
                result[key] = [item[:500] for item in values if item][:32]
            elif value:
                result[key] = value[:500]
            else:
                result[key] = []
            continue
        if key and stripped.startswith("-"):
            current = result.setdefault(key, [])
            if isinstance(current, list) and len(current) < 32:
                item = stripped.removeprefix("-").strip().strip("\\\"'")
                if item:
                    current.append(item[:500])
    return result


def _first_nonempty_line(content: str) -> str:
    for line in content.splitlines():
        clean = line.strip().lstrip("#").strip()
        if clean:
            return clean
    return ""
