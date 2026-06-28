"""HTML → markdown/text helpers (stdlib-only, Wave 2 web_fetch)."""

from __future__ import annotations

import re


def decode_entities(value: str) -> str:
    return (
        value.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )


def strip_tags(value: str) -> str:
    return decode_entities(re.sub(r"<[^>]+>", "", value))


def normalize_whitespace(value: str) -> str:
    text = value.replace("\r", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def html_to_markdown(html: str) -> tuple[str, str | None]:
    """Best-effort HTML to markdown; returns (body, optional title)."""
    title_match = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, re.I)
    title = (
        normalize_whitespace(strip_tags(title_match.group(1))) if title_match else None
    )
    text = html
    for pattern in (
        r"<script[\s\S]*?</script>",
        r"<style[\s\S]*?</style>",
        r"<noscript[\s\S]*?</noscript>",
    ):
        text = re.sub(pattern, "", text, flags=re.I)

    def link_repl(match: re.Match) -> str:
        href, body = match.group(1), match.group(2)
        label = normalize_whitespace(strip_tags(body))
        return f"[{label}]({href})" if label else href

    text = re.sub(
        r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
        link_repl,
        text,
        flags=re.I,
    )

    def heading_repl(match: re.Match) -> str:
        level = max(1, min(6, int(match.group(1))))
        label = normalize_whitespace(strip_tags(match.group(2)))
        return f"\n{'#' * level} {label}\n" if label else ""

    text = re.sub(
        r"<h([1-6])[^>]*>([\s\S]*?)</h\1>",
        heading_repl,
        text,
        flags=re.I,
    )

    def li_repl(match: re.Match) -> str:
        label = normalize_whitespace(strip_tags(match.group(1)))
        return f"\n- {label}" if label else ""

    text = re.sub(r"<li[^>]*>([\s\S]*?)</li>", li_repl, text, flags=re.I)
    text = re.sub(r"<(br|hr)\s*/?>", "\n", text, flags=re.I)
    text = re.sub(
        r"</(p|div|section|article|header|footer|table|tr|ul|ol)>",
        "\n",
        text,
        flags=re.I,
    )
    text = normalize_whitespace(strip_tags(text))
    return text, title


def truncate_text(value: str, max_chars: int) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    return value[:max_chars], True
