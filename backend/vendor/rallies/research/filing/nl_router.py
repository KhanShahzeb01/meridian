"""Natural-language routing for SEC filing sections (Wave 3 rank 9)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FilingRoute:
    form: str
    section_key: str
    label: str


# NL phrases → (preferred form, attribute on TenK / TenQ sections key)
_SECTION_PATTERNS: list[tuple[re.Pattern[str], str, str, str]] = [
    (re.compile(r"\brisk\s*factor", re.I), "10-K", "risk_factors", "Risk Factors (Item 1A)"),
    (re.compile(r"\bitem\s*1a\b", re.I), "10-K", "risk_factors", "Risk Factors (Item 1A)"),
    (re.compile(r"\bmd&?a\b|\bmanagement\s+discussion", re.I), "10-K", "management_discussion", "MD&A (Item 7)"),
    (re.compile(r"\bitem\s*7\b", re.I), "10-K", "management_discussion", "MD&A (Item 7)"),
    (re.compile(r"\bbusiness\s+description|\bbusiness\b|\bitem\s*1\b", re.I), "10-K", "business", "Business (Item 1)"),
    (re.compile(r"\bfinancial\s+statement", re.I), "10-K", "financials", "Financial Statements"),
    (re.compile(r"\bnotes\b|\bfootnote", re.I), "10-K", "notes", "Notes to Financial Statements"),
    (re.compile(r"\bsubsidiar", re.I), "10-K", "subsidiaries", "Subsidiaries"),
    (re.compile(r"\bquarterly\b|\b10-?q\b", re.I), "10-Q", "part_i_item_2", "MD&A (10-Q Part I Item 2)"),
]


def infer_form(query: str, explicit: str | None = None) -> str:
    if explicit:
        form = explicit.upper().replace("FORM", "").strip()
        if form in ("10-K", "10-Q", "8-K"):
            return form
    low = query.lower()
    if "10-q" in low or "quarter" in low or "quarterly" in low:
        return "10-Q"
    if "8-k" in low:
        return "8-K"
    return "10-K"


def route_filing_section(query: str, *, form: str | None = None) -> FilingRoute:
    """Map NL section text to edgartools form + section key."""
    resolved_form = infer_form(query, form)
    for pattern, default_form, section_key, label in _SECTION_PATTERNS:
        if pattern.search(query):
            use_form = default_form if default_form != "10-K" or resolved_form == "10-K" else resolved_form
            if default_form == "10-Q":
                use_form = "10-Q"
            return FilingRoute(form=use_form, section_key=section_key, label=label)

    # Default: risk factors on latest 10-K when query is vague
    return FilingRoute(
        form=resolved_form if resolved_form != "8-K" else "10-K",
        section_key="risk_factors" if resolved_form != "10-Q" else "part_i_item_2",
        label="Filing section (best match)",
    )
