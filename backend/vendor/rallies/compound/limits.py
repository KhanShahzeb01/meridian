"""Ticker limits: full watchlist/portfolio for compound context; batching for consensus."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import CompoundContext

# Standalone /ask or /debate when tickers are only inferred from question text
PERSONA_INLINE_TICKER_MAX = 5

# /consensus: one panel pass per batch (7 expert calls + summary per batch)
CONSENSUS_BATCH_SIZE = 6


def consensus_panel_ticker_order(
    tickers: list[str],
    compound_ctx: CompoundContext | None = None,
) -> list[str]:
    """
    Order tickers for the expert panel.

    When /portfolio is in compound context, portfolio holdings come first so
    batches cover actual positions before watchlist-only names.
    """
    if compound_ctx is None or not compound_ctx.tickers_by_source:
        return list(tickers)

    ordered: list[str] = []
    seen: set[str] = set()

    if "portfolio" in compound_ctx.sources:
        for t in compound_ctx.tickers_by_source.get("portfolio", []):
            if t and t not in seen:
                seen.add(t)
                ordered.append(t)

    for src in compound_ctx.sources:
        if src == "portfolio":
            continue
        for t in compound_ctx.tickers_by_source.get(src, []):
            if t and t not in seen:
                seen.add(t)
                ordered.append(t)

    for t in tickers:
        if t and t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def chunk_consensus_batches(
    tickers: list[str],
    *,
    compound_ctx: CompoundContext | None = None,
    batch_size: int = CONSENSUS_BATCH_SIZE,
) -> list[list[str]]:
    """Split ordered tickers into batches of at most batch_size for panel runs."""
    ordered = consensus_panel_ticker_order(tickers, compound_ctx)
    if batch_size < 1:
        batch_size = CONSENSUS_BATCH_SIZE
    return [ordered[i : i + batch_size] for i in range(0, len(ordered), batch_size)]
