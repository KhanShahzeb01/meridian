"""Resolve context commands that take a ticker argument after the token."""

from __future__ import annotations

import re
from typing import Any

from ..models import ParsedCommand
from .base import ResolverResult

_TICKER_AFTER = re.compile(r"^[A-Za-z]{1,6}(?:[.-][A-Za-z]{1,2})?")


def _ticker_after_command(prompt: str, cmd: ParsedCommand) -> str | None:
    from ...ticker_library import normalize_ticker_token

    tail = prompt[cmd.end :].lstrip()
    if not tail:
        return None
    token = tail.split()[0]
    sym = normalize_ticker_token(token)
    if sym:
        return sym
    return None


def resolve_quote(prompt: str, cmd: ParsedCommand, manager: Any | None) -> ResolverResult:
    ticker = _ticker_after_command(prompt, cmd)
    if not ticker:
        return ResolverResult(source="quote", notes=["Embedded /quote needs TICKER, e.g. /quote AAPL"])

    registry = getattr(manager, "data_registry", None) if manager else None
    yfs = registry.get_source("yfinance") if registry else None
    if not yfs:
        return ResolverResult(source="quote", tickers=[ticker], notes=["yfinance source unavailable"])

    data = yfs.get_quote(ticker)
    if not data or data.get("error"):
        return ResolverResult(source="quote", tickers=[ticker], notes=[f"Could not quote {ticker}"])

    parts = [f"## Quote — {ticker}"]
    for key, label in (
        ("price", "Price"),
        ("pe", "P/E"),
        ("market_cap", "Market cap"),
        ("sector", "Sector"),
    ):
        val = data.get(key)
        if val is not None:
            parts.append(f"- {label}: {val}")
    return ResolverResult(
        source="quote",
        tickers=[ticker],
        live_data_block="\n".join(parts),
        notes=[f"Quoted {ticker}."],
    )


def resolve_financials(prompt: str, cmd: ParsedCommand, manager: Any | None) -> ResolverResult:
    ticker = _ticker_after_command(prompt, cmd)
    if not ticker:
        return ResolverResult(
            source="financials",
            notes=["Embedded /financials needs TICKER, e.g. /financials AAPL"],
        )

    registry = getattr(manager, "data_registry", None) if manager else None
    yfs = registry.get_source("yfinance") if registry else None
    if not yfs:
        return ResolverResult(source="financials", tickers=[ticker], notes=["yfinance unavailable"])

    data = yfs.get_financials(ticker)
    if not data or data.get("error"):
        return ResolverResult(
            source="financials",
            tickers=[ticker],
            notes=[f"Could not load financials for {ticker}"],
        )

    lines = [f"## Financials — {ticker}"]
    for row in data.get("rows", [])[:8]:
        label = row.get("label", "")
        vals = row.get("values", [])
        if vals:
            lines.append(f"- {label}: {vals[0]}")
    return ResolverResult(
        source="financials",
        tickers=[ticker],
        live_data_block="\n".join(lines),
        notes=[f"Financials for {ticker}."],
    )
