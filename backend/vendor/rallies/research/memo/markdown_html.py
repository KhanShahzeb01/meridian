"""Lightweight markdown → HTML for memo expert analyses (no extra deps)."""

from __future__ import annotations

import html
import re

_VERDICT_LABELS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bstrong\s+sell\b", re.I), "Strong Sell"),
    (re.compile(r"\bstrong\s+buy\b", re.I), "Strong Buy"),
    (re.compile(r"\bwould\s+not\s+buy\b", re.I), "Sell"),
    (re.compile(r"\b(?:stay\s+out|would\s+avoid|pass\s+on)\b", re.I), "Sell"),
    (re.compile(r"\bnot\s+a\s+buy\b", re.I), "Sell"),
    (re.compile(r"\bwould\s+buy\b", re.I), "Buy"),
    (re.compile(r"\b(?:recommend\s+)?sell\b", re.I), "Sell"),
    (re.compile(r"\b(?:recommend\s+)?buy\b", re.I), "Buy"),
    (re.compile(r"\b(?:recommend\s+)?hold\b", re.I), "Hold"),
)


def normalize_verdict_label(text: str) -> str:
    """Map prose / markdown verdict to a short display label."""
    raw = str(text or "").strip()
    if not raw:
        return "—"

    structured = re.search(
        r"\*\*verdict:\*\*\s*(.+?)(?:\n|$)",
        raw,
        re.IGNORECASE,
    )
    if structured:
        raw = structured.group(1).strip()

    raw = re.sub(r"\*+", "", raw)
    head = raw.split("\n", 1)[0].strip()
    head = re.sub(r"^[–—-]\s*", "", head)
    head = head.split(" – ")[0].split(" - ")[0].strip()

    for pattern, label in _VERDICT_LABELS:
        if pattern.search(head) or pattern.search(raw[:800]):
            return label

    if len(head) <= 24 and head:
        return head.title()
    return "See analysis"


def _verdict_css_class(label: str) -> str:
    low = label.lower()
    if "strong buy" in low or low == "buy":
        return "verdict-buy"
    if "strong sell" in low or low == "sell":
        return "verdict-sell"
    if "hold" in low:
        return "verdict-hold"
    return "verdict-neutral"


def verdict_badge_html(label: str, confidence: str = "") -> str:
    css = _verdict_css_class(label)
    safe = html.escape(label)
    conf = html.escape(confidence.strip()) if confidence else ""
    conf_html = f'<span class="expert-confidence">{conf}</span>' if conf else ""
    return (
        f'<span class="expert-verdict-badge {css}">{safe}</span>{conf_html}'
    )


def _inline_format(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def _parse_table_row(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def _is_table_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", line))


def markdown_to_html(text: str, *, max_chars: int = 24_000) -> str:
    """Convert persona markdown to safe HTML fragments."""
    body = str(text or "").strip()
    if not body:
        return "<p><em>No analysis text.</em></p>"
    if len(body) > max_chars:
        body = body[:max_chars] + "\n\n… *(truncated)*"

    lines = body.splitlines()
    out: list[str] = []
    idx = 0
    in_ul = False
    in_ol = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()

        if not stripped:
            close_lists()
            idx += 1
            continue

        if stripped in ("---", "***", "___"):
            close_lists()
            out.append("<hr />")
            idx += 1
            continue

        if stripped.startswith("#### "):
            close_lists()
            out.append(f"<h4>{_inline_format(stripped[5:])}</h4>")
            idx += 1
            continue
        if stripped.startswith("### "):
            close_lists()
            out.append(f"<h3>{_inline_format(stripped[4:])}</h3>")
            idx += 1
            continue
        if stripped.startswith("## "):
            close_lists()
            out.append(f"<h3>{_inline_format(stripped[3:])}</h3>")
            idx += 1
            continue
        if stripped.startswith("# "):
            close_lists()
            out.append(f"<h2>{_inline_format(stripped[2:])}</h2>")
            idx += 1
            continue

        if "|" in stripped and stripped.count("|") >= 2:
            table_lines = []
            while idx < len(lines) and "|" in lines[idx]:
                table_lines.append(lines[idx])
                idx += 1
            if len(table_lines) >= 2:
                close_lists()
                header = _parse_table_row(table_lines[0])
                body_start = 1
                if len(table_lines) > 1 and _is_table_separator(table_lines[1]):
                    body_start = 2
                out.append('<table class="expert-table"><thead><tr>')
                out.extend(f"<th>{_inline_format(c)}</th>" for c in header)
                out.append("</tr></thead><tbody>")
                for row_line in table_lines[body_start:]:
                    if _is_table_separator(row_line):
                        continue
                    cells = _parse_table_row(row_line)
                    out.append("<tr>")
                    out.extend(f"<td>{_inline_format(c)}</td>" for c in cells)
                    out.append("</tr>")
                out.append("</tbody></table>")
                continue

        if re.match(r"^[-*]\s+", stripped):
            if not in_ul:
                close_lists()
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline_format(re.sub(r'^[-*]\s+', '', stripped))}</li>")
            idx += 1
            continue

        if re.match(r"^\d+\.\s+", stripped):
            if not in_ol:
                close_lists()
                out.append("<ol>")
                in_ol = True
            out.append(
                f"<li>{_inline_format(re.sub(r'^\d+\.\s+', '', stripped))}</li>"
            )
            idx += 1
            continue

        close_lists()
        out.append(f"<p>{_inline_format(stripped)}</p>")
        idx += 1

    close_lists()
    return "\n".join(out)
