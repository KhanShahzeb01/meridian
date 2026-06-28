"""Format slash-command output as clean markdown for the web UI."""

from __future__ import annotations

import re
from typing import Any, Optional

from services.market_data import (
    fred_vix_dict,
    finnhub_financials_dict,
    finnhub_quote_dict,
)


def _fmt_money(val: float | None, decimals: int = 2) -> str:
    if val is None:
        return "—"
    return f"${val:,.{decimals}f}"


def _fmt_pct(val: float | None, signed: bool = False) -> str:
    if val is None:
        return "—"
    if signed:
        return f"{val:+.2f}%"
    return f"{val:.2f}%"


def _fmt_mcap(val: float | None) -> str:
    if val is None:
        return "—"
    if val >= 1e12:
        return f"${val / 1e12:.2f}T"
    if val >= 1e9:
        return f"${val / 1e9:.2f}B"
    if val >= 1e6:
        return f"${val / 1e6:.1f}M"
    return f"${val:,.0f}"


def format_quote_markdown(data: dict[str, Any]) -> str:
    if not data or data.get("error"):
        err = data.get("error", "unavailable") if data else "unavailable"
        return f"**Could not fetch quote:** {err}"

    ticker = data.get("ticker", "")
    name = data.get("name") or ticker
    source = data.get("source", "live")
    as_of = data.get("as_of", "")

    rows: list[tuple[str, str]] = [
        ("Price", _fmt_money(data.get("price"))),
        ("Prev close", _fmt_money(data.get("prev_close"))),
        ("Change (1d)", _fmt_pct(data.get("change_pct"), signed=True)),
        ("Day high", _fmt_money(data.get("day_high"))),
        ("Day low", _fmt_money(data.get("day_low"))),
        ("Market cap", _fmt_mcap(data.get("market_cap"))),
        ("EPS (TTM)", _fmt_money(data.get("eps"))),
        ("P/E (TTM)", f"{data['pe']:.1f}" if data.get("pe") is not None else "—"),
        ("Fwd P/E", f"{data['pe_forward']:.1f}" if data.get("pe_forward") is not None else "—"),
        ("PEG (5yr)", f"{data['peg_5yr']:.2f}" if data.get("peg_5yr") is not None else "—"),
        ("Dividend yield", _fmt_pct(data.get("dividend_yield_pct"))),
        ("Sector", str(data.get("sector") or "—")),
    ]

    lines = [
        f"## {ticker} — {name}",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    for label, val in rows:
        if val != "—" or label in ("Price", "Prev close", "Sector"):
            lines.append(f"| {label} | {val} |")

    meta = f"*Source: {source}*"
    if as_of:
        meta += f" · *As of {as_of}*"
    lines.extend(["", meta])
    return "\n".join(lines)


def format_vix_markdown(data: dict[str, Any]) -> str:
    vix = data.get("vix")
    if vix is None or vix == "":
        return "**Could not fetch VIX data.**"
    lines = [
        "## CBOE Volatility Index (VIX)",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| VIX | {float(vix):.2f} |",
    ]
    if data.get("change") not in (None, ""):
        ch = data["change"]
        lines.append(f"| Change | {float(ch):+.2f}" if isinstance(ch, (int, float)) else f"| Change | {ch} |")
    if data.get("change_pct"):
        lines.append(f"| Change % | {data['change_pct']} |")
    if data.get("date"):
        lines.append("")
        lines.append(f"*Source: {data.get('source', 'fred')} · Date: {data['date']}*")
    return "\n".join(lines)


def format_news_markdown(ticker: str, manager: Any | None) -> str:
    finnhub = None
    if manager and hasattr(manager, "data_registry"):
        finnhub = manager.data_registry.get_source("finnhub")
    if not finnhub or not finnhub.available:
        return "**Finnhub API key required for news.**"
    result = finnhub.get_company_news(ticker, max_items=8)
    if not result or not result.data.get("headlines"):
        return f"**No recent news for {ticker}.**"
    lines = [
        f"## Latest news — {ticker}",
        "",
        "| Date | Source | Headline |",
        "| --- | --- | --- |",
    ]
    for art in result.data["headlines"]:
        headline = (art.get("headline") or "")[:100].replace("|", "/")
        lines.append(
            f"| {art.get('date', '')} | {art.get('source', '')} | {headline} |"
        )
    return "\n".join(lines)


def format_financials_markdown(ticker: str, manager: Any | None) -> str:
    yfs = manager.data_registry.get_source("yfinance") if manager and hasattr(manager, "data_registry") else None
    data = yfs.get_financials(ticker) if yfs else finnhub_financials_dict(ticker)
    if not data or data.get("error"):
        err = data.get("error", "unavailable") if data else "unavailable"
        return f"**No financials for {ticker}:** {err}"
    lines = [f"## {ticker} — annual income statement", ""]
    periods = data.get("periods") or []
    if not periods:
        return f"**No financial periods for {ticker}.**"
    header = "| Metric | " + " | ".join(periods) + " |"
    sep = "| --- | " + " | ".join(["---"] * len(periods)) + " |"
    lines.extend([header, sep])
    for row in data.get("rows") or []:
        vals = []
        for v in row.get("values") or []:
            if v is None:
                vals.append("—")
            elif isinstance(v, float) and abs(v) >= 1e9:
                vals.append(f"${v / 1e9:.2f}B")
            elif isinstance(v, float) and abs(v) >= 1e6:
                vals.append(f"${v / 1e6:.1f}M")
            elif isinstance(v, float):
                vals.append(f"{v:.2f}")
            else:
                vals.append(str(v))
        lines.append(f"| {row.get('label', '')} | " + " | ".join(vals) + " |")
    lines.extend(["", f"*Source: {data.get('source', 'live')}*"])
    return "\n".join(lines)


def format_peers_markdown(ticker: str, manager: Any | None) -> str:
    finnhub = manager.data_registry.get_source("finnhub") if manager and hasattr(manager, "data_registry") else None
    if not finnhub or not finnhub.available:
        return "**Finnhub API key required for peers.**"
    result = finnhub.get_peers(ticker)
    if not result:
        return f"**No peer data for {ticker}.**"
    peers = [t for t in result.data.get("peers", [])[:6] if t != ticker]
    all_tickers = [ticker] + peers
    yfs = manager.data_registry.get_source("yfinance") if manager else None
    lines = [
        f"## Peer comparison — {ticker}",
        "",
        "| Ticker | Price | P/E | Market cap |",
        "| --- | --- | --- | --- |",
    ]
    for sym in all_tickers:
        data = yfs.get_quote(sym) if yfs else finnhub_quote_dict(sym)
        if not data or data.get("error"):
            lines.append(f"| {sym} | — | — | — |")
            continue
        pe = f"{data['pe']:.1f}" if data.get("pe") is not None else "—"
        lines.append(
            f"| {sym} | {_fmt_money(data.get('price'))} | {pe} | {_fmt_mcap(data.get('market_cap'))} |"
        )
    return "\n".join(lines)


def format_macro_markdown(manager: Any | None) -> str:
    fred = manager.data_registry.get_source("fred") if manager and hasattr(manager, "data_registry") else None
    if not fred or not fred.available:
        return "**FRED API key required for macro data.** Set `FRED_API_KEY`."
    result = fred.get_macro_summary()
    if not result or not getattr(result, "data", None):
        return "**Could not fetch macro data.**"
    lines = [
        "## Economic dashboard",
        "",
        "| Indicator | Value | Date | Previous |",
        "| --- | --- | --- | --- |",
    ]
    for sid in ["FEDFUNDS", "CPIAUCSL", "UNRATE", "DGS10", "DGS2", "T10Y2Y", "GDPC1", "SP500"]:
        entry = result.data.get(sid)
        if not entry:
            continue
        val = entry.get("value", "")
        prev = entry.get("previous")
        prev_str = f"{prev:.2f}" if isinstance(prev, float) else "—"
        if isinstance(val, float):
            if sid in ("GDPC1", "SP500"):
                val_str = f"{val:,.0f}"
            elif sid == "CPIAUCSL":
                val_str = f"{val:.1f}"
            else:
                val_str = f"{val:.2f}%"
        else:
            val_str = str(val)
        lines.append(
            f"| {entry.get('label', sid)} | {val_str} | {entry.get('date', '')} | {prev_str} |"
        )
    return "\n".join(lines)


def format_earnings_calendar_markdown(manager: Any | None) -> str:
    finnhub = manager.data_registry.get_source("finnhub") if manager and hasattr(manager, "data_registry") else None
    if not finnhub or not finnhub.available:
        return "**Finnhub API key required for earnings calendar.**"
    result = finnhub.get_earnings_calendar()
    if not result:
        return "**Could not fetch earnings calendar.**"
    earnings = result.data.get("earnings", [])
    if not earnings:
        return "**No upcoming earnings in the next 14 days.**"
    lines = [
        "## Upcoming earnings (next 14 days)",
        "",
        "| Date | Ticker | Quarter | EPS est. | Hour |",
        "| --- | --- | --- | --- | --- |",
    ]
    for e in earnings[:15]:
        q = f"Q{e.get('quarter', '')}" if e.get("quarter") else ""
        lines.append(
            f"| {e.get('date', '')} | {e.get('ticker', '')} | {q} | "
            f"{e.get('estimate', '')} | {e.get('hour', '')} |"
        )
    return "\n".join(lines)


def _ticker_from_routed(routed: str) -> Optional[str]:
    parts = routed.strip().split()
    if len(parts) < 2:
        return None
    sym = parts[1].upper().lstrip("$")
    if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,5}", sym):
        return sym
    return None


def format_command_markdown(
    cmd_type: str,
    routed: str,
    manager: Any | None,
) -> Optional[str]:
    """Return clean markdown for data commands; None → use raw console output."""
    routed_l = routed.strip().lower()
    if cmd_type == "quote" or routed_l.startswith("/quote"):
        ticker = _ticker_from_routed(routed)
        if not ticker:
            return None
        yfs = None
        if manager and hasattr(manager, "data_registry"):
            yfs = manager.data_registry.get_source("yfinance")
        data = yfs.get_quote(ticker) if yfs else finnhub_quote_dict(ticker)
        return format_quote_markdown(data or {"ticker": ticker, "error": "no data"})

    if cmd_type == "vix" or routed_l.startswith("/vix"):
        cboe = None
        if manager and hasattr(manager, "data_registry"):
            cboe = manager.data_registry.get_source("cboe")
        if cboe:
            result = cboe.get_vix()
            if result and result.data:
                return format_vix_markdown(result.data)
        fred = fred_vix_dict()
        return format_vix_markdown(fred or {})

    if cmd_type == "news" or routed_l.startswith("/news"):
        ticker = _ticker_from_routed(routed)
        if ticker:
            return format_news_markdown(ticker, manager)

    if cmd_type == "financials" or routed_l.startswith("/financials"):
        ticker = _ticker_from_routed(routed)
        if ticker:
            return format_financials_markdown(ticker, manager)

    if routed_l.startswith("/peers"):
        ticker = _ticker_from_routed(routed)
        if ticker:
            return format_peers_markdown(ticker, manager)

    if cmd_type == "macro" or routed_l == "/macro" or routed_l.startswith("/macro "):
        return format_macro_markdown(manager)

    if routed_l == "/earnings":
        return format_earnings_calendar_markdown(manager)

    return None
