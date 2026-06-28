"""Memo table of contents and reading guide."""

from __future__ import annotations

import html
import re

# (anchor id, display title) — order matches memo-template.html
MEMO_SECTIONS: tuple[tuple[str, str], ...] = (
    ("sec-metrics", "Key Metrics"),
    ("sec-charts", "Charts & Visuals"),
    ("sec-variant", "Variant View"),
    ("sec-thesis", "Thesis"),
    ("sec-business", "Business"),
    ("sec-priced-in", "What's Priced In"),
    ("sec-valuation", "Valuation Analysis"),
    ("sec-scenarios", "Scenarios"),
    ("sec-catalysts", "Catalysts"),
    ("sec-risks", "Risks & Tripwires"),
    ("sec-position", "Position Management"),
    ("sec-monitoring", "Monitoring KPIs"),
    ("sec-experts", "Expert Opinions"),
    ("sec-references", "References & Data Sources"),
)


def build_table_of_contents() -> str:
    """Clickable ordered list linking to section anchors."""
    items = "".join(
        f'<li><a href="#{sec_id}">{html.escape(title)}</a></li>'
        for sec_id, title in MEMO_SECTIONS
    )
    return f'<ol class="memo-toc-list">{items}</ol>'


def _strip_tags(text: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", str(text or ""))
    return re.sub(r"\s+", " ", plain).strip()


def build_memo_guide(slots: dict[str, str]) -> str:
    """
    Short reading guide at the top of the memo.

    Uses LLM-authored memo_guide when present; otherwise builds from trade header.
    """
    if slots.get("memo_guide") and len(_strip_tags(slots["memo_guide"])) > 40:
        body = slots["memo_guide"].strip()
        if not body.startswith("<"):
            body = f"<p>{html.escape(body)}</p>"
        return body

    ticker = html.escape(str(slots.get("ticker") or "—"))
    company = html.escape(str(slots.get("company_name") or ticker))
    direction = html.escape(str(slots.get("direction") or "—"))
    horizon = html.escape(str(slots.get("horizon") or "—"))
    conviction = html.escape(str(slots.get("conviction") or "—"))
    target = html.escape(str(slots.get("price_target_base") or "—"))
    upside = html.escape(str(slots.get("upside_pct") or "—"))
    variant = html.escape(_strip_tags(slots.get("variant_view") or "")[:280])

    intro = (
        f"<p>This memo is a structured <strong>{direction}</strong> thesis on "
        f"<strong>{company}</strong> ({ticker}) over a <strong>{horizon}</strong> "
        f"horizon. Conviction is <strong>{conviction}</strong>; base-case target "
        f"<strong>${target}</strong> ({upside} upside). Use the table of contents "
        f"below to jump to any section.</p>"
    )
    if variant and variant != "—":
        intro += f'<p class="guide-variant"><em>{variant}</em></p>'

    path = (
        "<p><strong>Suggested reading path:</strong></p>"
        "<ol class=\"guide-path\">"
        "<li><a href=\"#sec-metrics\">Key Metrics</a> &amp; "
        "<a href=\"#sec-charts\">Charts</a> — live valuation context</li>"
        "<li><a href=\"#sec-variant\">Variant View</a> &amp; "
        "<a href=\"#sec-thesis\">Thesis</a> — core idea and falsifiable bullets</li>"
        "<li><a href=\"#sec-valuation\">Valuation</a> &amp; "
        "<a href=\"#sec-scenarios\">Scenarios</a> — base/bull/bear framing</li>"
        "<li><a href=\"#sec-risks\">Risks</a> &amp; "
        "<a href=\"#sec-catalysts\">Catalysts</a> — what could go wrong or accelerate</li>"
        "<li><a href=\"#sec-experts\">Expert Opinions</a> — independent persona views</li>"
        "<li><a href=\"#sec-position\">Position</a> &amp; "
        "<a href=\"#sec-monitoring\">KPIs</a> — sizing and what to watch</li>"
        "</ol>"
    )
    return intro + path


def build_memo_navigation(slots: dict[str, str]) -> dict[str, str]:
    """Slots for guide + TOC (call after narrative slots are merged)."""
    return {
        "table_of_contents": build_table_of_contents(),
        "memo_guide": build_memo_guide(slots),
    }
