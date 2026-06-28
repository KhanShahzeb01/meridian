"""Optional memory updates from research tool results (graph path)."""

from __future__ import annotations

from typing import Any

from ..reducers import append_tool_result, set_market_snapshot


def record_tool_in_memory(
    memory: dict[str, Any],
    *,
    tool_name: str,
    arguments: dict[str, Any],
    result: str,
) -> dict[str, Any]:
    """Append a compact tool record; snapshot quote-like tools by ticker."""
    entry = {
        "tool": tool_name,
        "arguments": arguments,
        "preview": result[:500],
    }
    memory["tool_results"] = append_tool_result(
        list(memory.get("tool_results") or []),
        entry,
    )
    for ticker in _tickers_from_arguments(arguments):
        if _is_quote_like_tool(tool_name):
            memory["market_snapshots"] = set_market_snapshot(
                dict(memory.get("market_snapshots") or {}),
                ticker,
                result[:2000],
            )
    return memory


def _tickers_from_arguments(arguments: dict[str, Any]) -> list[str]:
    tickers: list[str] = []
    raw = arguments.get("ticker")
    if raw:
        tickers.append(str(raw).strip().upper())
    group = arguments.get("tickers")
    if isinstance(group, list):
        for item in group:
            sym = str(item).strip().upper()
            if sym and sym not in tickers:
                tickers.append(sym)
    return tickers


def _is_quote_like_tool(tool_name: str) -> bool:
    return tool_name in {
        "research_fetch",
        "research_fetch_multi",
        "gather_equity_bundle",
    }
