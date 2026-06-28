"""Parse Rich console panel output into structured sections for the web UI."""

from __future__ import annotations

import re
from typing import Any

PANEL_HEADER = re.compile(r"^╭[─\s]*(.*?)[\s─]*╮\s*$")
PANEL_ROW = re.compile(r"^│(.*)│\s*$")
PANEL_FOOTER = re.compile(r"^╰")
RICH_TAGS = re.compile(r"\[/?[a-z_]+\]", re.IGNORECASE)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
MULTI_NEWLINE = re.compile(r"\n{3,}")
THINKING_LINE = re.compile(r"^Thinking:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _strip_markup(text: str) -> str:
    if not text:
        return ""
    text = ANSI_ESCAPE.sub("", text)
    text = RICH_TAGS.sub("", text)
    lines = []
    for line in text.split("\n"):
        line = line.replace("\u2502", "|").replace("\u2503", "|")
        line = line.replace("\u2514", " ").replace("\u2500", "-")
        stripped = line.strip()
        if stripped.startswith("●"):
            line = f"- {stripped[1:].strip()}"
        lines.append(line.rstrip())
    text = "\n".join(lines)
    return MULTI_NEWLINE.sub("\n\n", text).strip()


def parse_rich_panels(raw: str) -> list[dict[str, str]]:
    """Extract titled Rich panels from captured console output."""
    if not raw:
        return []

    panels: list[dict[str, str]] = []
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        header = PANEL_HEADER.match(line)
        if not header:
            i += 1
            continue

        title = header.group(1).strip()
        i += 1
        content_lines: list[str] = []
        while i < len(lines) and not PANEL_FOOTER.match(lines[i]):
            row = PANEL_ROW.match(lines[i])
            if row:
                content_lines.append(row.group(1).rstrip())
            elif lines[i].strip():
                content_lines.append(lines[i].rstrip())
            i += 1

        panels.append({"title": title, "content": "\n".join(content_lines).strip()})
        i += 1

    return panels


def _remove_panel_blocks(raw: str) -> str:
    """Return text outside Rich panel borders."""
    if not raw:
        return ""
    kept: list[str] = []
    in_panel = False
    for line in raw.splitlines():
        if PANEL_HEADER.match(line):
            in_panel = True
            continue
        if in_panel:
            if PANEL_FOOTER.match(line):
                in_panel = False
            continue
        kept.append(line)
    return "\n".join(kept)


def _normalize_markdown(text: str) -> str:
    if not text:
        return ""
    lines = [ln.rstrip() for ln in text.splitlines()]
    # Drop empty leading/trailing lines while preserving paragraph breaks.
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def extract_sections(raw: str) -> dict[str, Any]:
    """Map Rich output to query-adjacent sections for the Meridian web UI."""
    panels = parse_rich_panels(raw)
    leftover = _remove_panel_blocks(raw)

    planning_parts: list[str] = []
    thinking_parts: list[str] = []
    response_parts: list[str] = []
    other_panels: list[dict[str, str]] = []

    for panel in panels:
        title = panel["title"].strip()
        title_key = title.lower()
        content = _normalize_markdown(_strip_markup(panel["content"]))
        if not content:
            continue
        if title_key == "planning":
            planning_parts.append(content)
        elif title_key in {"thinking", "reasoning"}:
            thinking_parts.append(content)
        elif title_key == "response":
            response_parts.append(content)
        elif title_key == "query":
            continue
        else:
            other_panels.append({"title": title, "content": content})

    for match in THINKING_LINE.finditer(leftover):
        snippet = match.group(1).strip()
        if snippet:
            thinking_parts.append(snippet)

    extra = _normalize_markdown(_strip_markup(leftover))
    # Remove thinking lines from extra noise.
    extra = THINKING_LINE.sub("", extra).strip()
    extra = _normalize_markdown(extra)

    planning = _normalize_markdown("\n\n".join(planning_parts))
    thinking = _normalize_markdown("\n\n".join(thinking_parts))
    response = _normalize_markdown("\n\n".join(response_parts))

    if not response and other_panels:
        response = _normalize_markdown(
            "\n\n".join(f"## {p['title']}\n\n{p['content']}" for p in other_panels)
        )
        other_panels = []

    if not response:
        response = _normalize_markdown(_strip_markup(raw))

    # Avoid duplicating the same body in response + extra (causes double render in UI).
    if response and extra:
        if extra.strip() == response.strip() or extra.strip() in response:
            extra = None
        elif response.strip() in extra:
            response = extra
            extra = None

    return {
        "planning": planning or None,
        "thinking": thinking or None,
        "response": response or None,
        "panels": other_panels or None,
        "extra": extra or None,
    }


def primary_content(sections: dict[str, Any], raw: str) -> str:
    """Best single string for backward-compatible `content` field."""
    for key in ("response", "planning", "thinking", "extra"):
        value = sections.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _strip_markup(raw)
