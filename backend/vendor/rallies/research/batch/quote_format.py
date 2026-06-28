"""Format yfinance quote lines for agent / bundle output."""

from __future__ import annotations


def format_quote_line(ticker: str, data: dict) -> str | None:
    if not data or data.get("error"):
        return None
    parts = [f"{ticker}:"]
    if data.get("price"):
        parts.append(f"Price ${data['price']}")
    if data.get("prev_close"):
        parts.append(f"Prev Close ${data['prev_close']}")
    if data.get("pe"):
        parts.append(f"P/E {data['pe']}")
    if data.get("pe_forward"):
        parts.append(f"Fwd P/E {data['pe_forward']}")
    if data.get("peg_5yr"):
        parts.append(f"PEG {data['peg_5yr']}")
    if data.get("eps"):
        parts.append(f"EPS {data['eps']}")
    if data.get("dividend_yield_pct"):
        parts.append(f"Yield {data['dividend_yield_pct']:.2f}%")
    if data.get("market_cap"):
        parts.append(f"Mkt Cap ${data['market_cap']:,.0f}")
    if data.get("sector"):
        parts.append(f"Sector {data['sector']}")
    return " | ".join(parts)
