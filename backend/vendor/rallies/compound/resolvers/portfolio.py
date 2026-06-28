"""Resolve /portfolio context (holdings list + optional quotes)."""

from __future__ import annotations

from typing import Any

from ...portfolio_names import (
    DEFAULT_PORTFOLIO,
    extract_portfolio_name_after_command,
)
from ...research.units import DOLLAR_UNIT_RULES, format_usd_literal
from .base import ResolverResult


def _format_qty(quantity: float) -> str:
    q = float(quantity)
    if abs(q - round(q)) < 1e-9:
        return str(int(round(q)))
    return f"{q:.6f}".rstrip("0").rstrip(".")


def _quote_price(registry: Any | None, ticker: str) -> float | None:
    if not registry:
        return None
    yfs = registry.get_source("yfinance")
    if not yfs:
        return None
    data = yfs.get_quote(ticker)
    if not data or data.get("error"):
        return None
    price = data.get("price")
    return float(price) if price is not None else None


def resolve_portfolio(
    manager: Any | None,
    prompt: str = "",
    *,
    command_end: int | None = None,
) -> ResolverResult:
    storage = getattr(manager, "storage", None) if manager else None
    notes: list[str] = []
    known = (
        {n["name"] for n in storage.portfolio_list_names()}
        if storage
        else None
    )
    if prompt and command_end is not None:
        portfolio_name, name_note = extract_portfolio_name_after_command(
            prompt, command_end, known_names=known
        )
        if name_note:
            notes.append(name_note)
    else:
        portfolio_name = DEFAULT_PORTFOLIO
    if storage is None:
        return ResolverResult(
            source="portfolio",
            notes=["No storage available — portfolio empty."],
        )

    items = storage.portfolio_list(portfolio_name)
    tickers = list(
        dict.fromkeys(
            str(item["ticker"]).upper()
            for item in items
            if item.get("ticker")
        )
    )

    if not tickers:
        block = (
            f"## Portfolio — {portfolio_name} (compound context)\n\n"
            f"**No positions in portfolio '{portfolio_name}'.**\n\n"
            f"Add holdings first, e.g. "
            f"`/portfolio {portfolio_name} add TICKER QTY AVG_PRICE`.\n\n"
            f"Check lists with `/portfolio portfolios`. "
            f"Default holdings live in portfolio `default`."
        )
        return ResolverResult(
            source="portfolio",
            tickers=[],
            live_data_block=block,
            notes=notes
            + [
                f"Portfolio '{portfolio_name}' is empty — persona will see this message."
            ],
        )

    registry = getattr(manager, "data_registry", None) if manager else None
    lines = [
        f"## Portfolio holdings — {portfolio_name} (compound context)",
        DOLLAR_UNIT_RULES,
        "",
        "Computed position values (shares × current price, literal USD):",
    ]
    total_value = 0.0
    priced_count = 0
    for item in items:
        t = str(item.get("ticker", "")).upper()
        qty = float(item.get("quantity") or 0)
        cost = float(item.get("cost_basis") or 0)
        price = _quote_price(registry, t)
        qty_s = _format_qty(qty)
        cost_total = qty * cost
        if price is not None and qty > 0:
            value = qty * price
            total_value += value
            priced_count += 1
            lines.append(
                f"- {t}: {_format_qty(qty)} sh, avg cost {format_usd_literal(cost)}/sh, "
                f"price {format_usd_literal(price)}/sh, "
                f"position value {format_usd_literal(value)} "
                f"(cost basis {format_usd_literal(cost_total)})"
            )
        else:
            lines.append(
                f"- {t}: {_format_qty(qty)} sh, avg cost {format_usd_literal(cost)}/sh, "
                f"position value unavailable (no live price), "
                f"cost basis {format_usd_literal(cost_total)}"
            )

    if priced_count:
        lines.append("")
        lines.append(
            f"**Total portfolio market value** (sum of priced positions): "
            f"{format_usd_literal(total_value)}"
        )

    block = "\n".join(lines)
    return ResolverResult(
        source="portfolio",
        tickers=tickers,
        live_data_block=block,
        notes=notes
        + [f"Loaded {len(tickers)} ticker(s) from portfolio '{portfolio_name}'."],
    )
