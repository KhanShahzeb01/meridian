"""Shared helpers for named watchlist/portfolio resolution in compound lines."""

from __future__ import annotations

from typing import Callable

# Words that often follow /portfolio or /watchlist in natural questions — not list names.
COMPOUND_CONTEXT_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "the",
        "my",
        "our",
        "your",
        "all",
        "any",
        "each",
        "from",
        "for",
        "with",
        "on",
        "in",
        "to",
        "of",
        "at",
        "by",
        "or",
        "please",
        "now",
        "today",
        "current",
        "holdings",
        "holding",
        "positions",
        "position",
        "stocks",
        "stock",
        "tickers",
        "ticker",
        "names",
        "name",
        "data",
        "optimize",
        "optimization",
        "rebalance",
        "rebalancing",
        "suggest",
        "suggestions",
        "analyze",
        "analysis",
        "review",
        "check",
        "compare",
        "rank",
        "pick",
        "best",
        "worst",
        "trim",
        "losers",
        "winners",
    }
)


def resolve_named_list_after_command(
    token: str,
    *,
    default: str,
    known_names: set[str] | None,
    normalize: Callable[[str], str],
    is_likely: Callable[[str], bool],
    prefix_hint: str,
) -> tuple[str, str | None]:
    """
    Pick list name from token after /watchlist or /portfolio in a compound prompt.

    Returns (resolved_name, optional_note).
    """
    low = token.lower()
    if not token or low in COMPOUND_CONTEXT_STOPWORDS:
        return default, None
    if not is_likely(token):
        return default, None

    name = normalize(token)
    if name.startswith(prefix_hint):
        return name, None

    if known_names is not None:
        if name in known_names:
            return name, None
        return (
            default,
            f"List '{name}' not found; using '{default}'.",
        )

    return name, None
