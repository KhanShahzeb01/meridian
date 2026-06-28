"""Fetch SEC filing sections via edgartools (Wave 3 rank 9)."""

from __future__ import annotations

import logging
from typing import Any

from .nl_router import FilingRoute, route_filing_section

logger = logging.getLogger(__name__)

MAX_SECTION_CHARS = 120_000


def _import_edgar():
    try:
        from edgar import Company, set_identity

        try:
            set_identity("Rallies CLI (research@rallies.ai)")
        except Exception:
            pass
        return Company
    except ImportError:
        return None


def _section_text(obj: Any, route: FilingRoute) -> str | None:
    key = route.section_key
    if hasattr(obj, key):
        val = getattr(obj, key)
        if val is not None:
            return str(val).strip() or None
    sections = getattr(obj, "sections", None)
    if sections is not None:
        if hasattr(sections, "get"):
            val = sections.get(key)
            if val is not None:
                return str(val).strip() or None
        if hasattr(sections, key):
            val = getattr(sections, key)
            if val is not None:
                return str(val).strip() or None
    return None


def fetch_filing_section(
    ticker: str,
    section_query: str,
    *,
    form: str | None = None,
    max_chars: int = MAX_SECTION_CHARS,
) -> dict[str, Any]:
    """
    Fetch one filing section for a ticker using edgartools.

    Returns dict with keys: ticker, form, section, label, text, filing_date, truncated, error.
    """
    ticker = ticker.upper().strip()
    route = route_filing_section(section_query, form=form)
    Company = _import_edgar()
    if Company is None:
        return {
            "ticker": ticker,
            "error": "edgartools not installed. pip install 'rallies[sources]'",
        }

    try:
        company = Company(ticker)
        filings = company.get_filings(form=route.form)
        filing = filings.latest(1)
        if filing is None:
            return {
                "ticker": ticker,
                "form": route.form,
                "error": f"No {route.form} filing found for {ticker}",
            }
        obj = filing.obj()
        if obj is None:
            return {
                "ticker": ticker,
                "form": route.form,
                "error": "Could not parse filing object",
            }
        text = _section_text(obj, route)
        if not text:
            return {
                "ticker": ticker,
                "form": route.form,
                "section": route.section_key,
                "label": route.label,
                "filing_date": str(getattr(filing, "filing_date", "")),
                "error": f"Section '{route.section_key}' not available on this {route.form}",
            }
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars] + "\n\n...[section truncated]..."
        return {
            "ticker": ticker,
            "form": route.form,
            "section": route.section_key,
            "label": route.label,
            "filing_date": str(getattr(filing, "filing_date", "")),
            "text": text,
            "truncated": truncated,
        }
    except Exception as e:
        logger.warning("fetch_filing_section failed for %s: %s", ticker, e)
        return {"ticker": ticker, "error": str(e)}


def format_filing_section(result: dict[str, Any]) -> str:
    if result.get("error"):
        return f"Filing error ({result.get('ticker', '?')}): {result['error']}"
    header = (
        f"## {result.get('ticker')} — {result.get('label')} "
        f"({result.get('form')}, filed {result.get('filing_date', '')})"
    )
    body = result.get("text") or ""
    if result.get("truncated"):
        header += "\n*(truncated for display)*"
    return f"{header}\n\n{body}"
