"""Merge resolver outputs into one CompoundContext."""

from __future__ import annotations

from .models import CompoundContext
from .resolvers.base import ResolverResult


def merge_resolver_results(results: list[ResolverResult]) -> CompoundContext:
    ctx = CompoundContext()
    ticker_seen: set[str] = set()
    blocks: list[str] = []

    for res in results:
        if res.source and res.source not in ctx.sources:
            ctx.sources.append(res.source)
        if res.source and res.tickers:
            ctx.tickers_by_source[res.source] = list(res.tickers)
        for t in res.tickers:
            if t not in ticker_seen:
                ticker_seen.add(t)
                ctx.tickers.append(t)
        if res.live_data_block.strip():
            src = res.source or "context"
            blocks.append(f"### Resolved context: {src}\n{res.live_data_block.strip()}")
        ctx.notes.extend(res.notes)

    if blocks:
        ctx.live_data_block = "\n\n".join(blocks)
    return ctx
