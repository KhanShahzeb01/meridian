"""Parallel quote + SEC fetch for a single ticker (Wave 2 rank 7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .executor import run_parallel_tasks
from .quote_format import format_quote_line
from .sec_format import format_recent_filings_block


@dataclass(frozen=True)
class BundleRecord:
    tool_name: str
    query_suffix: str
    line: str


def _fetch_quote(registry: Any, ticker: str) -> str | None:
    yfs = registry.get_source("yfinance") if registry else None
    if not yfs:
        return None
    return format_quote_line(ticker, yfs.get_quote(ticker))


def _fetch_sec(registry: Any, ticker: str, form: str = "8-K") -> str | None:
    edgar = registry.get_source("edgartools") if registry else None
    if not edgar:
        return None
    filings = edgar.get_recent_filings(ticker, form=form, count=5)
    return format_recent_filings_block(ticker, filings, form=form)


def parallel_quote_sec_bundle(
    registry: Any,
    ticker: str,
    *,
    sec_form: str = "8-K",
    include_sec: bool = True,
) -> list[BundleRecord]:
    """
    Fetch quote and recent SEC filings concurrently.
    Returns records ready for scratchpad / agent line assembly.
    """
    ticker = ticker.upper().strip()
    tasks: dict[str, Any] = {"quote": lambda: _fetch_quote(registry, ticker)}
    if include_sec:
        tasks["sec"] = lambda: _fetch_sec(registry, ticker, form=sec_form)

    outcomes = run_parallel_tasks(tasks)
    records: list[BundleRecord] = []

    quote = outcomes.get("quote")
    if isinstance(quote, str) and quote:
        records.append(
            BundleRecord("yfinance_quote", ticker, quote),
        )
    elif isinstance(quote, Exception):
        records.append(
            BundleRecord(
                "yfinance_quote",
                ticker,
                f"{ticker}: [quote fetch error: {quote}]",
            ),
        )

    if include_sec:
        sec = outcomes.get("sec")
        if isinstance(sec, str) and sec:
            records.append(
                BundleRecord("edgartools_sec_filings", f"{ticker}|{sec_form}", sec),
            )
        elif isinstance(sec, Exception):
            records.append(
                BundleRecord(
                    "edgartools_sec_filings",
                    f"{ticker}|{sec_form}",
                    f"\n--- {ticker} SEC ---\n  [error: {sec}]",
                ),
            )

    return records


def bundle_to_text(records: list[BundleRecord]) -> str:
    return "\n".join(r.line for r in records if r.line)
