"""Build compact memory digest text from rallies state slices."""

from __future__ import annotations

from typing import Any

from ..state import RalliesState
from .digest_sections import (
    format_prefetch_note,
    format_snapshots_section,
    format_tickers_section,
    format_tool_results_section,
    merge_ticker_lists,
)
from .marker import SESSION_MEMORY_MARKER


def _entities_block(state: dict[str, Any]) -> dict[str, Any]:
    entities = state.get("entities")
    return entities if isinstance(entities, dict) else {}


def _memory_block(state: dict[str, Any]) -> dict[str, Any]:
    memory = state.get("memory")
    return memory if isinstance(memory, dict) else {}


def memory_digest_from_slice(state_slice: dict[str, Any]) -> str:
    """Build digest from entities + memory buckets (no full tool payloads)."""
    entities = _entities_block(state_slice)
    memory = _memory_block(state_slice)

    tickers = merge_ticker_lists(
        entities.get("query_tickers"),
        entities.get("active_tickers"),
        entities.get("compound_tickers"),
    )
    sections = [
        format_tickers_section(tickers),
        format_snapshots_section(memory.get("market_snapshots") or {}),
        format_prefetch_note(memory.get("prefetched_market_block")),
        format_tool_results_section(memory.get("tool_results") or []),
    ]
    body = "\n\n".join(section for section in sections if section.strip())
    if not body.strip():
        return ""
    return f"{SESSION_MEMORY_MARKER}\n\n{body}"


def memory_digest(state: RalliesState) -> str:
    """Build digest from a full RalliesState."""
    return memory_digest_from_slice(
        {
            "entities": dict(state["entities"]),
            "memory": dict(state["memory"]),
        }
    )
