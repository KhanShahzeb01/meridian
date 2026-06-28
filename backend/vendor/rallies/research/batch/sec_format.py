"""Format EDGAR recent filings for agent / bundle output."""

from __future__ import annotations


def format_recent_filings_block(
    ticker: str,
    filings: list[dict] | dict | None,
    *,
    form: str = "8-K",
) -> str | None:
    if not filings:
        return None
    if isinstance(filings, dict) and filings.get("error"):
        return None
    lines = [f"\n--- {ticker} Recent {form} Filings (SEC) ---"]
    for row in filings[:5]:
        if not isinstance(row, dict):
            continue
        date = row.get("date", "")
        ftype = row.get("form", form)
        desc = (row.get("description") or "")[:100]
        lines.append(f"  {date} | {ftype} | {desc}")
    return "\n".join(lines) if len(lines) > 1 else None
