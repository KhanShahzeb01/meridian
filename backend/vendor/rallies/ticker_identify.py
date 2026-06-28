"""
Ticker identification with explicit modes.

User queries: use $SYMBOL (e.g. $AAPL $MSFT) so prose is never mistaken for tickers.

Session / follow-up: look back through the thread for $SYMBOL first, then rallies
quote lines (AAPL | Apple Inc.), then company parentheticals (NVIDIA (NVDA)).
Finance abbreviations in tables — (TTM), (FCF), (EPS) — are never tickers.
"""

from __future__ import annotations

import re
from enum import Enum

from .ticker_abbrev_blocklist import is_finance_abbrev
from .ticker_library import DOLLAR_TICKER_RE, extract_dollar_tickers

_PAREN_TICKER_RE = re.compile(r"\(([A-Z]{2,6}(?:\.[A-Z])?(?:-[A-Z])?)\)")
_SESSION_FOLLOWUP_RE = re.compile(r"\n*\[Session follow-up[^\]]*\]\s*", re.DOTALL)
# Ticker column in rallies/yfinance lines — must be followed by company name, not a number.
_BOX_PIPE_CHARS = "│┃|"
_QUOTE_TABLE_RE = re.compile(
    r"(?m)(?:^|\n)\s*(?:\|\s*)?(?:-\s*)?"
    r"([A-Z]{2,6}(?:\.[A-Z])?(?:-[A-Z])?)\s+\|\s+(?=[A-Za-z])"
)
_SCREENER_SCORE_LINE_RE = re.compile(
    r"(?m)^\s*([A-Z]{1,6}(?:\.[A-Z])?(?:-[A-Z])?)\s+—\s+Avg\s+",
)


class TickerExtractionMode(str, Enum):
    """How aggressively to infer symbols from text."""

    QUERY = "query"  # user question — $SYMBOL (+ rallies quote tables in pasted output)
    SESSION = "session"  # prior thread / assistant answers
    COMPARE = "compare"  # legacy alias for QUERY


def _add_candidate(found: list[str], symbol: str) -> None:
    sym = symbol.upper().strip()
    if len(sym) <= 1 or is_finance_abbrev(sym):
        return
    if sym not in found:
        found.append(sym)


def sanitize_ticker_list(symbols: list[str] | tuple[str, ...]) -> list[str]:
    """Drop finance abbreviations and duplicates while preserving order."""
    cleaned: list[str] = []
    for symbol in symbols:
        sym = str(symbol or "").strip().upper()
        if not sym or is_finance_abbrev(sym):
            continue
        if sym not in cleaned:
            cleaned.append(sym)
    return cleaned


def _content_for_ticker_scan(content: str) -> str:
    """Strip injected follow-up hints so they never become tickers."""
    return _SESSION_FOLLOWUP_RE.sub("", content or "").strip()


def _dollar_tickers(text: str) -> list[str]:
    return extract_dollar_tickers(_content_for_ticker_scan(text))


def _normalize_table_pipes(text: str) -> str:
    """Rich tables use box-drawing │; normalize to ASCII | for parsing."""
    if not text:
        return ""
    out = str(text)
    for ch in _BOX_PIPE_CHARS:
        out = out.replace(ch, "|")
    return out


def _quote_table_tickers(text: str) -> list[str]:
    found: list[str] = []
    normalized = _normalize_table_pipes(text or "")
    for match in _QUOTE_TABLE_RE.finditer(normalized):
        _add_candidate(found, match.group(1))
    return found


def _screener_score_line_tickers(text: str) -> list[str]:
    """SNDK — Avg 9.0/10 lines from /screen agent score blocks."""
    found: list[str] = []
    for match in _SCREENER_SCORE_LINE_RE.finditer(text or ""):
        _add_candidate(found, match.group(1))
    return found


def _paren_company_tickers(text: str) -> list[str]:
    """(NVDA) yes; (TTM) / (FCF) no."""
    found: list[str] = []
    for match in _PAREN_TICKER_RE.finditer(text or ""):
        _add_candidate(found, match.group(1))
    return found


def _merge_ticker_groups(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for sym in group:
            if sym not in merged:
                merged.append(sym)
    return merged


def identify_tickers(
    text: str,
    *,
    mode: TickerExtractionMode = TickerExtractionMode.QUERY,
) -> list[str]:
    """
    Identify ticker symbols from a single text blob.

    Modes:
    - QUERY: $SYMBOL plus rallies quote-table rows (pasted output)
    - SESSION: $SYMBOL, quote-table rows, filtered company parentheticals
    - COMPARE: same as QUERY
    """
    if not text or not str(text).strip():
        return []

    effective = (
        TickerExtractionMode.QUERY
        if mode == TickerExtractionMode.COMPARE
        else mode
    )

    dollar = _dollar_tickers(text)
    table = _quote_table_tickers(text)
    screener = _screener_score_line_tickers(text)
    paren = _paren_company_tickers(text)

    if effective == TickerExtractionMode.QUERY:
        return _merge_ticker_groups(dollar, table, screener, paren)

    return _merge_ticker_groups(dollar, table, screener, paren)[:5]


def identify_session_tickers(text: str) -> list[str]:
    """Extraction for assistant replies and session context."""
    return identify_tickers(text, mode=TickerExtractionMode.SESSION)


def identify_query_tickers(text: str) -> list[str]:
    """Extraction for the current user question ($SYMBOL primary)."""
    return identify_tickers(text, mode=TickerExtractionMode.QUERY)


def tickers_from_conversation(
    messages: list[dict],
    *,
    max_symbols: int = 5,
) -> list[str]:
    """
    Collect session tickers by scanning the thread (newest messages first).

    Priority tiers (within each tier, recency wins):
    1. $SYMBOL in any user or assistant message
    2. Quote-table rows from assistant replies (AAPL | Apple Inc.)
    3. Company parentheticals from assistant replies (NVIDIA (NVDA))
    """
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        content = _content_for_ticker_scan(str(msg.get("content") or ""))
        screen = _merge_ticker_groups(
            _quote_table_tickers(content),
            _screener_score_line_tickers(content),
        )
        if screen:
            return sanitize_ticker_list(screen)[:max_symbols]

    dollar_ordered: list[str] = []
    table_ordered: list[str] = []
    paren_ordered: list[str] = []

    for msg in reversed(messages):
        if msg.get("role") not in ("user", "assistant"):
            continue
        content = _content_for_ticker_scan(str(msg.get("content") or ""))

        for sym in _dollar_tickers(content):
            if sym not in dollar_ordered:
                dollar_ordered.append(sym)

        if msg.get("role") == "assistant":
            for sym in _quote_table_tickers(content):
                if sym not in table_ordered:
                    table_ordered.append(sym)
            for sym in _screener_score_line_tickers(content):
                if sym not in table_ordered:
                    table_ordered.append(sym)
            for sym in _paren_company_tickers(content):
                if sym not in paren_ordered:
                    paren_ordered.append(sym)

    merged = sanitize_ticker_list(
        _merge_ticker_groups(dollar_ordered, table_ordered, paren_ordered)
    )
    return merged[:max_symbols]


def tickers_from_last_assistant(
    messages: list[dict],
    *,
    max_symbols: int = 5,
) -> list[str]:
    """Tickers named in the most recent assistant reply (e.g. after /screen)."""
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        content = _content_for_ticker_scan(str(msg.get("content") or ""))
        found = identify_session_tickers(content)
        return found[:max_symbols]
    return []


def session_focus_tickers(
    messages: list[dict],
    candidates: list[str],
    *,
    max_symbols: int = 5,
) -> list[str]:
    """
    Tickers to name in a follow-up hint.

    Prefer symbols the user explicitly marked with $ earlier in the thread.
    """
    dollar_in_thread: list[str] = []
    for msg in messages:
        if msg.get("role") not in ("user", "assistant"):
            continue
        content = _content_for_ticker_scan(str(msg.get("content") or ""))
        for sym in _dollar_tickers(content):
            if sym not in dollar_in_thread:
                dollar_in_thread.append(sym)

    if dollar_in_thread:
        focused = [sym for sym in dollar_in_thread if sym in candidates]
        if focused:
            return focused[:max_symbols]
        return dollar_in_thread[:max_symbols]

    return [sym for sym in candidates if not is_finance_abbrev(sym)][:max_symbols]


def parse_consensus_prompt(prompt: str) -> tuple[list[str], str]:
    """
    Extract $tickers and preserve natural-language instructions from /consensus.
    """
    text = (prompt or "").strip()
    if text.lower().startswith("/consensus"):
        text = text[len("/consensus") :].strip()
    tickers = identify_query_tickers(text)
    return tickers, text
