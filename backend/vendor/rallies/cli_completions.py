"""Prompt completion helpers (slash commands + $TICKER anywhere in the line)."""

from __future__ import annotations

import re
from typing import Iterator

from .ticker_library import suggest_tickers

# Kept in sync with rallies.cli.SLASH_COMMANDS
SLASH_COMMANDS: tuple[str, ...] = (
    "/help",
    "/compound_help",
    "/key",
    "/history",
    "/export",
    "/resume",
    "/clear",
    "/compact",
    "/example",
    "/tickers",
    "/tickers add",
    "/tickers remove",
    "/tickers list",
    "/watchlist",
    "/watchlist add",
    "/watchlist remove",
    "/quote",
    "/financials",
    "/sec",
    "/earnings",
    "/news",
    "/peers",
    "/insider",
    "/holdings",
    "/macro",
    "/hedgefund",
    "/index",
    "/vix",
    "/searchsec",
    "/sector",
    "/portfolio",
    "/portfolio add",
    "/portfolio remove",
    "/alert",
    "/alerts",
    "/screen",
    "/optimize",
    "/dcf",
    "/options",
    "/analysis",
    "/chart",
    "/personas",
    "/rules",
    "/soul",
    "/fetch",
    "/bundle",
    "/skill",
    "/memo",
    "/filing",
    "/research",
    "/research-log",
    "/ask",
    "/debate",
    "/exit",
    "/quit",
    "/consensus",
)

_TICKER_FRAGMENT_RE = re.compile(r"^[^\s,]*$")


def ticker_completion_fragment(text_before_cursor: str) -> str | None:
    """
    Return the partial symbol after the nearest $ if completion applies.

    Works after slash commands (/research $AAP) and in free text (compare $AAP).
    Returns None when not in a completable $-token (e.g. after space following a symbol).
    """
    if not text_before_cursor or "$" not in text_before_cursor:
        return None
    dollar_idx = text_before_cursor.rfind("$")
    fragment = text_before_cursor[dollar_idx + 1 :]
    if not _TICKER_FRAGMENT_RE.fullmatch(fragment):
        return None
    return fragment


def iter_ticker_completion_rows(text_before_cursor: str, *, limit: int = 30) -> Iterator[dict]:
    fragment = ticker_completion_fragment(text_before_cursor)
    if fragment is None:
        return
    yield from suggest_tickers(fragment.upper(), limit=limit)


def should_offer_slash_completions(text_before_cursor: str) -> bool:
    """Only complete the first slash token (before any space)."""
    stripped = (text_before_cursor or "").lstrip()
    return stripped.startswith("/") and " " not in stripped


def iter_slash_command_completions(text_before_cursor: str) -> Iterator[str]:
    if not should_offer_slash_completions(text_before_cursor):
        return
    stripped = text_before_cursor.lstrip()
    for cmd in SLASH_COMMANDS:
        if cmd.startswith(stripped):
            yield cmd
