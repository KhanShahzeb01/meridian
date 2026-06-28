"""Record planner rounds and step outputs into RalliesState memory."""

from __future__ import annotations

from typing import Any

from ..reducers import append_plan, append_tool_result, set_market_snapshot


def record_plan_generated(
    memory: dict[str, Any],
    *,
    round_num: int,
    plan: list[dict[str, Any]],
) -> dict[str, Any]:
    entry = {
        "round": round_num,
        "status": "generated",
        "steps": [
            {"title": item.get("title"), "description": item.get("description")}
            for item in plan
        ],
    }
    memory["plans"] = append_plan(list(memory.get("plans") or []), entry)
    return memory


def record_plan_step_completed(
    memory: dict[str, Any],
    *,
    title: str,
    description: str,
    result: str,
    summary: str,
) -> dict[str, Any]:
    memory["plans"] = append_plan(
        list(memory.get("plans") or []),
        {
            "status": "completed",
            "title": title,
            "description": description,
            "summary": summary[:500],
        },
    )
    memory["tool_results"] = append_tool_result(
        list(memory.get("tool_results") or []),
        {
            "tool": "planner_action",
            "arguments": {"title": title, "description": description},
            "preview": str(result)[:500],
        },
    )
    ticker = _guess_ticker_from_text(f"{title} {description}")
    if ticker and result.strip():
        memory["market_snapshots"] = set_market_snapshot(
            dict(memory.get("market_snapshots") or {}),
            ticker,
            str(result)[:2000],
        )
    return memory


def _guess_ticker_from_text(text: str) -> str | None:
    from ...ticker_abbrev_blocklist import is_finance_abbrev
    from ...ticker_library import extract_dollar_tickers

    dollar = extract_dollar_tickers(text)
    if dollar:
        return dollar[0]

    import re

    match = re.search(r"\b([A-Z]{1,5}(?:[.-][A-Z]{1,2})?)\b", text.upper())
    if not match:
        return None
    symbol = match.group(1)
    if symbol in {"THE", "AND", "FOR", "WITH", "FROM"}:
        return None
    if is_finance_abbrev(symbol):
        return None
    return symbol
