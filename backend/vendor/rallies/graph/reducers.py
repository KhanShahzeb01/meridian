"""Pure reducer helpers for merging RalliesState slices (LangGraph-ready)."""

from __future__ import annotations

from typing import Any

DEFAULT_TOOL_RESULT_CAP = 50


def append_messages(
    existing: list[dict[str, Any]],
    new_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Append-only reducer for thread / workspace messages."""
    if not new_messages:
        return list(existing)
    merged = list(existing)
    merged.extend(new_messages)
    return merged


def merge_market_snapshots(
    existing: dict[str, str],
    updates: dict[str, str],
) -> dict[str, str]:
    """Merge by ticker key; later values overwrite earlier ones."""
    merged = dict(existing)
    for ticker, snapshot in updates.items():
        key = str(ticker).strip().upper()
        if not key:
            continue
        merged[key] = str(snapshot)
    return merged


def set_market_snapshot(
    existing: dict[str, str],
    ticker: str,
    snapshot: str,
) -> dict[str, str]:
    """Set a single ticker snapshot."""
    return merge_market_snapshots(existing, {ticker: snapshot})


def append_tool_result(
    existing: list[dict[str, Any]],
    entry: dict[str, Any],
    *,
    max_results: int = DEFAULT_TOOL_RESULT_CAP,
) -> list[dict[str, Any]]:
    """Append tool result with a rolling cap."""
    merged = list(existing)
    merged.append(dict(entry))
    overflow = len(merged) - max(1, max_results)
    if overflow > 0:
        merged = merged[overflow:]
    return merged


def append_plan(
    existing: list[dict[str, Any]],
    plan_entry: dict[str, Any],
) -> list[dict[str, Any]]:
    """Append one planner round or step record."""
    merged = list(existing)
    merged.append(dict(plan_entry))
    return merged
