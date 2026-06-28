"""Shared formatting for yfinance quote dicts (ticker + company name + metrics)."""

from __future__ import annotations


def format_yfinance_quote_line(data: dict) -> str:
    """One snapshot line for prompts; includes company name when available."""
    if not data or data.get("error"):
        ticker = (data or {}).get("ticker") or "?"
        return f"{ticker}: quote unavailable"

    ticker = str(data.get("ticker") or "?").upper()
    parts = [ticker]
    name = (data.get("name") or "").strip()
    if name:
        parts.append(name)
    if data.get("price") is not None:
        parts.append(f"Price ${float(data['price']):.2f}")
    if data.get("prev_close") is not None:
        parts.append(f"Prev Close ${float(data['prev_close']):.2f}")
    if data.get("pe") is not None:
        parts.append(f"P/E {float(data['pe']):.1f}")
    if data.get("pe_forward") is not None:
        parts.append(f"Fwd P/E {float(data['pe_forward']):.1f}")
    if data.get("peg_5yr") is not None:
        parts.append(f"PEG {float(data['peg_5yr']):.2f}")
    if data.get("eps") is not None:
        parts.append(f"EPS {float(data['eps']):.2f}")
    if data.get("dividend_yield_pct") is not None:
        parts.append(f"Yield {float(data['dividend_yield_pct']):.2f}%")
    if data.get("market_cap") is not None:
        parts.append(f"Mkt Cap ${float(data['market_cap']):,.0f}")
    if data.get("sector"):
        parts.append(f"Sector {data['sector']}")
    if data.get("change_pct") is not None:
        parts.append(f"Chg {float(data['change_pct']):+.2f}%")
    return " | ".join(parts)
