"""Format individual sections of the memory digest."""

from __future__ import annotations

from typing import Any

MAX_SNAPSHOT_CHARS = 400
MAX_TOOL_PREVIEW_CHARS = 200
MAX_TOOL_ROWS = 8


def merge_ticker_lists(*groups: list[str] | None) -> list[str]:
    from ...ticker_identify import sanitize_ticker_list

    raw: list[str] = []
    for group in groups:
        if not group:
            continue
        for item in group:
            sym = str(item).strip().upper()
            if sym and sym not in raw:
                raw.append(sym)
    return sanitize_ticker_list(raw)


def format_tickers_section(tickers: list[str]) -> str:
    if not tickers:
        return ""
    return "### Active tickers\n" + ", ".join(tickers)


def format_snapshots_section(snapshots: dict[str, str]) -> str:
    if not snapshots:
        return ""
    lines = ["### Market snapshots"]
    for ticker in sorted(snapshots):
        body = str(snapshots[ticker] or "").strip()
        if not body:
            continue
        if len(body) > MAX_SNAPSHOT_CHARS:
            body = body[: MAX_SNAPSHOT_CHARS - 3] + "..."
        lines.append(f"**{ticker}**: {body}")
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def _format_tool_arguments(arguments: dict[str, Any]) -> str:
    ticker = arguments.get("ticker")
    if ticker:
        return f"ticker={ticker}"
    tickers = arguments.get("tickers")
    if isinstance(tickers, list) and tickers:
        joined = ",".join(str(t).upper() for t in tickers[:5])
        return f"tickers={joined}"
    intent = arguments.get("intent")
    if intent:
        return f"intent={intent}"
    return "args=…"


def format_tool_results_section(tool_results: list[dict[str, Any]]) -> str:
    if not tool_results:
        return ""
    lines = ["### Recent tools (summaries only)"]
    recent = tool_results[-MAX_TOOL_ROWS:]
    for entry in recent:
        if not isinstance(entry, dict):
            continue
        tool = str(entry.get("tool") or "tool")
        args = entry.get("arguments")
        arg_text = _format_tool_arguments(args) if isinstance(args, dict) else "args=…"
        preview = str(entry.get("preview") or "").strip()
        if len(preview) > MAX_TOOL_PREVIEW_CHARS:
            preview = preview[: MAX_TOOL_PREVIEW_CHARS - 3] + "..."
        lines.append(f"- `{tool}` ({arg_text}) → {preview or '(no preview)'}")
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def format_prefetch_note(prefetch: str | None) -> str:
    text = str(prefetch or "").strip()
    if not text:
        return ""
    if len(text) > MAX_SNAPSHOT_CHARS:
        text = text[: MAX_SNAPSHOT_CHARS - 3] + "..."
    return "### Prefetched compare block\n" + text
