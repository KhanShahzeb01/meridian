"""Resolve /watchlist context without printing the full table."""

from __future__ import annotations

from typing import Any

from ...watchlist_names import (
    DEFAULT_WATCHLIST,
    extract_watchlist_name_after_command,
)
from .base import ResolverResult


def resolve_watchlist(
    manager: Any | None,
    prompt: str = "",
    *,
    command_end: int | None = None,
) -> ResolverResult:
    storage = getattr(manager, "storage", None) if manager else None
    notes: list[str] = []
    known = (
        {n["name"] for n in storage.watchlist_list_names()}
        if storage
        else None
    )
    if prompt and command_end is not None:
        watchlist_name, name_note = extract_watchlist_name_after_command(
            prompt, command_end, known_names=known
        )
        if name_note:
            notes.append(name_note)
    else:
        watchlist_name = DEFAULT_WATCHLIST
    if storage is None:
        return ResolverResult(
            source="watchlist",
            notes=["No storage available — watchlist empty."],
        )

    items = storage.watchlist_list(watchlist_name)
    tickers = [
        str(item["ticker"]).upper()
        for item in items
        if item.get("ticker") and "/" not in str(item["ticker"])
    ]
    tickers = list(dict.fromkeys(tickers))
    # Storage lists newest-first; compound context uses stable insertion order (oldest first).
    tickers.reverse()

    if not tickers:
        block = (
            f"## Watchlist — {watchlist_name} (compound context)\n\n"
            f"**No tickers in watchlist '{watchlist_name}'.**\n\n"
            f"Add symbols first, e.g. "
            f"`/watchlist {watchlist_name} add TICKER` or "
            f"`/watchlist {watchlist_name} MU`.\n\n"
            f"Check lists with `/watchlist watchlists`. "
            f"Default symbols live in watchlist `default`."
        )
        return ResolverResult(
            source="watchlist",
            tickers=[],
            live_data_block=block,
            notes=notes
            + [
                f"Watchlist '{watchlist_name}' is empty — persona will see this message."
            ],
        )

    block = _build_watchlist_block(tickers, manager, watchlist_name=watchlist_name)
    note = f"Loaded {len(tickers)} ticker(s) from watchlist '{watchlist_name}'."

    return ResolverResult(
        source="watchlist",
        tickers=tickers,
        live_data_block=block,
        notes=notes + [note],
    )


def _build_watchlist_block(
    tickers: list[str],
    manager: Any | None,
    *,
    watchlist_name: str = DEFAULT_WATCHLIST,
) -> str:
    registry = getattr(manager, "data_registry", None) if manager else None
    if registry:
        return _block_from_registry(registry, tickers, watchlist_name=watchlist_name)
    return _block_from_yfinance(tickers, watchlist_name=watchlist_name)


def _block_from_registry(
    registry: Any, tickers: list[str], *, watchlist_name: str = DEFAULT_WATCHLIST
) -> str:
    yfs = registry.get_source("yfinance")
    if not yfs:
        return _block_from_yfinance(tickers, watchlist_name=watchlist_name)

    header = (
        "## Watchlist snapshot (compound context)"
        if watchlist_name == DEFAULT_WATCHLIST
        else f"## Watchlist snapshot — {watchlist_name} (compound context)"
    )
    lines = [
        header,
        "Use these figures for ranking and comparison. Do not invent prices.",
        "mkt cap is company size (not your position size). Share prices are per-share USD.",
    ]
    from ...quotes import format_yfinance_quote_line

    for ticker in tickers:
        data = yfs.get_quote(ticker)
        if not data or data.get("error"):
            lines.append(f"- {ticker}: quote unavailable")
            continue
        if not data.get("ticker"):
            data = {**data, "ticker": ticker}
        lines.append("- " + format_yfinance_quote_line(data))
    return "\n".join(lines)


def _block_from_yfinance(tickers: list[str], *, watchlist_name: str = DEFAULT_WATCHLIST) -> str:
    try:
        import yfinance as yf
    except ImportError:
        return (
            "## Watchlist tickers\n"
            + ", ".join(tickers)
            + "\n(yfinance not installed — install rallies[sources])"
        )

    header = (
        "## Watchlist snapshot (compound context)"
        if watchlist_name == DEFAULT_WATCHLIST
        else f"## Watchlist snapshot — {watchlist_name} (compound context)"
    )
    lines = [header, "Tickers: " + ", ".join(tickers)]
    for ticker in tickers:
        try:
            from ...yfinance_metrics import info_snapshot

            snap = info_snapshot(yf.Ticker(ticker).info or {})
            line = f"- {ticker}"
            if snap.get("price"):
                line += f" | ${float(snap['price']):.2f}"
            if snap.get("pe_trailing") is not None:
                line += f" | P/E {float(snap['pe_trailing']):.1f}"
            if snap.get("peg_5yr") is not None:
                line += f" | PEG {float(snap['peg_5yr']):.2f}"
            lines.append(line)
        except Exception:
            lines.append(f"- {ticker}: fetch error")
    return "\n".join(lines)
