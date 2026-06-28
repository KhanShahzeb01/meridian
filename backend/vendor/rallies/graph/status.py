"""Format checkpoint status for /graph-status."""

from __future__ import annotations

from typing import Any

from .checkpoint import checkpoint_db_path
from .checkpoint_runtime import load_shadow_graph_values
from .flags import (
    graph_checkpoints_enabled,
    graph_planner_enabled,
    graph_research_enabled,
    langgraph_available,
    turn_pair_memory_enabled,
)


def _tickers_from_rallies(rallies: dict[str, Any]) -> list[str]:
    entities = rallies.get("entities")
    if not isinstance(entities, dict):
        return []
    active = entities.get("active_tickers") or []
    query = entities.get("query_tickers") or []
    merged: list[str] = []
    for group in (query, active):
        if not isinstance(group, list):
            continue
        for item in group:
            sym = str(item).strip().upper()
            if sym and sym not in merged:
                merged.append(sym)
    return merged


def _tool_result_count(rallies: dict[str, Any]) -> int:
    memory = rallies.get("memory")
    if not isinstance(memory, dict):
        return 0
    results = memory.get("tool_results")
    if not isinstance(results, list):
        return 0
    return len(results)


def build_graph_status_lines(manager: Any | None) -> list[str]:
    """Human-readable status rows for the REPL."""
    lines = [
        "[bold]LangGraph status[/bold]",
        f"Planner graph: {'yes' if graph_planner_enabled() else 'no'} "
        f"(set RALLIES_GRAPH_PLANNER=1)",
        f"Research graph: {'yes' if graph_research_enabled() else 'no'} "
        f"(set RALLIES_GRAPH_RESEARCH=1)",
        f"Checkpoints: {'yes' if graph_checkpoints_enabled() else 'no'} "
        f"(set RALLIES_GRAPH_CHECKPOINTS=1)",
        f"Turn-pair memory: {'yes' if turn_pair_memory_enabled() else 'no'} "
        f"(set RALLIES_GRAPH_MEMORY=1 or RALLIES_GRAPH_PLANNER=1)",
        f"langgraph installed: {'yes' if langgraph_available() else 'no'}",
        f"DB: {checkpoint_db_path()}",
    ]

    history_session = getattr(manager, "history_session", None) if manager else None
    session_id = str((history_session or {}).get("id") or "").strip()
    if turn_pair_memory_enabled() and session_id:
        try:
            from .memory.session_store import load_turn_pairs

            pair_count = len(load_turn_pairs(session_id))
            lines.append(f"Turn pairs stored: {pair_count}")
        except Exception:
            pass

    if not session_id:
        lines.append("Thread id: (no active history session)")
        return lines

    lines.append(f"Thread id: {session_id}")
    values = load_shadow_graph_values(session_id)
    if not values:
        lines.append("Checkpoint: none for this session yet")
        return lines

    last_node = str(values.get("last_node") or "")
    rallies = values.get("rallies")
    if not isinstance(rallies, dict):
        lines.append("Checkpoint: present but rallies payload missing")
        return lines

    tickers = _tickers_from_rallies(rallies)
    tool_count = _tool_result_count(rallies)
    raw_prompt = ""
    input_block = rallies.get("input")
    if isinstance(input_block, dict):
        raw_prompt = str(input_block.get("raw_prompt") or "")

    lines.append(f"Last node: {last_node or '(unknown)'}")
    lines.append(f"Tickers: {', '.join(tickers) if tickers else '(none)'}")
    lines.append(f"Tool results in memory: {tool_count}")
    if raw_prompt:
        preview = raw_prompt if len(raw_prompt) <= 80 else raw_prompt[:77] + "..."
        lines.append(f"Last prompt: {preview}")

    return lines
