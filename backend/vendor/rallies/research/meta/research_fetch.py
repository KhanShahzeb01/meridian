"""Meta-tool: route NL intent to rallies data sources (Wave 3 rank 10)."""

from __future__ import annotations

import re
from typing import Any

from ..batch.quote_format import format_quote_line
from ..batch.ticker_bundle import parallel_quote_sec_bundle
from ..filing.section_fetch import fetch_filing_section, format_filing_section


def _intent_bucket(intent: str) -> str:
    low = intent.lower()
    if any(w in low for w in ("margin", "financial", "revenue", "income", "earnings", "profit", "statement")):
        return "financials"
    if any(w in low for w in ("risk", "filing", "10-k", "10-q", "sec", "md&a", "mda")):
        return "filing"
    if any(w in low for w in ("news", "headline")):
        return "news"
    if any(w in low for w in ("insider", "form 4")):
        return "insider"
    if any(w in low for w in ("quote", "price", "pe", "market cap")):
        return "quote"
    if any(
        w in low
        for w in (
            "hedge fund",
            "hedgefund",
            "form pf",
            "systemic risk",
            "repo market",
            "ofr",
            "leverage ratio",
            "financial stability",
        )
    ):
        return "hedgefund"
    if any(w in low for w in ("macro", "economy", "fed", "cpi", "gdp")):
        return "macro"
    if any(w in low for w in ("vix", "volatility")):
        return "vix"
    return "bundle"


def _format_financials(data: dict[str, Any], *, include_margins: bool) -> str:
    if not data or data.get("error"):
        return f"Financials error: {data.get('error', 'unknown')}"
    lines = [f"## {data.get('ticker')} financials"]
    periods = data.get("periods") or []
    rows = {r["label"]: r for r in data.get("rows", [])}

    def row_line(label: str) -> str | None:
        r = rows.get(label)
        if not r:
            return None
        vals = []
        for i, v in enumerate(r.get("values") or []):
            period = periods[i] if i < len(periods) else ""
            if v is None:
                continue
            if abs(v) >= 1e9:
                vals.append(f"{period}: ${v/1e9:.2f}B")
            elif abs(v) >= 1e6:
                vals.append(f"{period}: ${v/1e6:.2f}M")
            else:
                vals.append(f"{period}: {v:.2f}")
        return f"{label}: " + " | ".join(vals) if vals else None

    for label in (
        "Total Revenue",
        "Gross Profit",
        "Operating Income",
        "Net Income",
        "EBITDA",
        "Earnings Per Share",
    ):
        line = row_line(label)
        if line:
            lines.append(line)

    if include_margins:
        rev = rows.get("Total Revenue")
        if rev:
            rev_vals = rev.get("values") or []
            for numer_label, margin_name in (
                ("Gross Profit", "Gross margin"),
                ("Operating Income", "Operating margin"),
                ("Net Income", "Net margin"),
            ):
                numer = rows.get(numer_label)
                if not numer:
                    continue
                mvals = []
                for i, rv in enumerate(rev_vals):
                    nv = (numer.get("values") or [None] * len(rev_vals))[i]
                    if rv and nv is not None and rv != 0:
                        pct = 100.0 * nv / rv
                        period = periods[i] if i < len(periods) else ""
                        mvals.append(f"{period}: {pct:.1f}%")
                if mvals:
                    lines.append(f"{margin_name}: " + " | ".join(mvals))
    return "\n".join(lines)


def research_fetch(
    registry: Any,
    ticker: str,
    intent: str,
) -> str:
    """
    Single NL entry point wrapping rallies sources.

    Used by /research tool loop and callable directly in tests.
    """
    ticker = ticker.upper().strip()
    bucket = _intent_bucket(intent)
    yfs = registry.get_source("yfinance") if registry else None

    if bucket == "quote" and yfs:
        data = yfs.get_quote(ticker)
        line = format_quote_line(ticker, data or {})
        return line or f"No quote for {ticker}"

    if bucket == "financials" and yfs:
        data = yfs.get_financials(ticker, years=4)
        include_margins = "margin" in intent.lower()
        return _format_financials(data or {}, include_margins=include_margins)

    if bucket == "filing":
        result = fetch_filing_section(ticker, intent)
        return format_filing_section(result)

    if bucket == "news":
        finnhub = registry.get_source("finnhub") if registry else None
        if finnhub and finnhub.available:
            result = finnhub.get_company_news(ticker, max_items=5)
            headlines = (result.data or {}).get("headlines", []) if result else []
            lines = [f"## {ticker} news"]
            for art in headlines[:5]:
                hl = (art.get("headline") or "")[:120]
                src = art.get("source") or ""
                lines.append(f"- [{src}] {hl}")
            return "\n".join(lines) if len(lines) > 1 else f"No news for {ticker}"
        return f"Finnhub unavailable for {ticker} news"

    if bucket == "insider":
        edgar = registry.get_source("edgartools") if registry else None
        if edgar:
            trades = edgar.get_insider_trades(ticker, count=5) or []
            lines = [f"## {ticker} insider trades"]
            for txn in trades:
                if txn.get("info"):
                    lines.append(str(txn["info"]))
                elif txn.get("error"):
                    lines.append(str(txn["error"]))
                else:
                    lines.append(
                        f"{txn.get('date')} | {txn.get('owner')} | {txn.get('type')} | "
                        f"{txn.get('shares')} @ {txn.get('price')}"
                    )
            return "\n".join(lines)
        return f"edgartools unavailable for {ticker} insider data"

    if bucket == "hedgefund":
        from .market_snapshots import hedgefund_snapshot

        return hedgefund_snapshot(registry)

    if bucket == "macro":
        from .market_snapshots import macro_snapshot

        return macro_snapshot(registry)

    if bucket == "vix":
        cboe = registry.get_source("cboe") if registry else None
        if cboe:
            result = cboe.get_vix()
            v = result.data if result else {}
            return f"VIX: {v.get('vix')} (change {v.get('change_pct')}%)"
        return "CBOE VIX unavailable"

    # Default bundle: quote + recent SEC
    if registry:
        records = parallel_quote_sec_bundle(registry, ticker)
        if records:
            return "\n".join(r.line for r in records if r.line)
    return f"No data returned for {ticker} (intent: {intent})"


def research_fetch_multi(
    registry: Any,
    tickers: list[str],
    intent: str,
) -> str:
    """Fetch same intent for multiple tickers (compare workflows)."""
    parts = []
    for ticker in tickers[:5]:
        parts.append(research_fetch(registry, ticker, intent))
    return "\n\n".join(parts)


def extract_compare_tickers(query: str) -> list[str]:
    from ...ticker_identify import identify_query_tickers

    return identify_query_tickers(query)[:5]
