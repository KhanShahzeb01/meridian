"""Finance / metric abbreviations that must never be treated as tickers."""

from __future__ import annotations

# Uppercase symbols commonly seen as (TTM), (FCF), etc. in metric tables.
FINANCE_ABBREV_BLOCKLIST: frozenset[str] = frozenset(
    {
        "ATH",
        "ATL",
        "CAGR",
        "CFO",
        "CEO",
        "CPI",
        "DCF",
        "EBIT",
        "EBITDA",
        "EPS",
        "ETF",
        "FCF",
        "FDA",
        "FED",
        "FY",
        "GAAP",
        "GDP",
        "IPO",
        "LTM",
        "NAV",
        "PEG",
        "PE",
        "ROA",
        "ROE",
        "SEC",
        "TTM",
        "USD",
        "YOY",
        "YTD",
    }
)


def is_finance_abbrev(symbol: str) -> bool:
    """True when a token is a metric label, not a tradable symbol."""
    return str(symbol or "").strip().upper() in FINANCE_ABBREV_BLOCKLIST
