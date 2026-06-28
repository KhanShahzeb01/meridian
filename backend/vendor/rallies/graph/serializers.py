"""Serialize and deserialize RalliesState for checkpoints and debug dumps."""

from __future__ import annotations

import json
from typing import Any

from .defaults import (
    create_empty_state,
    empty_control_state,
    empty_entities_state,
    empty_input_state,
    empty_memory_state,
    empty_output_state,
    empty_research_state,
    empty_session_state,
    empty_thread_state,
)
from .state import ControlState, InputState, RalliesState, ThreadState


def _coerce_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _coerce_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def session_from_dict(data: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_session_state()
    if not isinstance(data, dict):
        return base
    return {
        "id": _coerce_str(data.get("id"), base["id"]),
        "started_at": _coerce_str(data.get("started_at"), base["started_at"]),
        "file_path": _coerce_str(data.get("file_path"), base["file_path"]),
        "tier": _coerce_str(data.get("tier"), base["tier"]),
        "thread_max_tokens": _coerce_int(
            data.get("thread_max_tokens"),
            base["thread_max_tokens"],
        ),
    }


def input_from_dict(data: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_input_state()
    if not isinstance(data, dict):
        return base
    raw = _coerce_str(data.get("raw_prompt"), base["raw_prompt"])
    effective = _coerce_str(data.get("effective_prompt"), raw)
    return InputState(raw_prompt=raw, effective_prompt=effective)


def entities_from_dict(data: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_entities_state()
    if not isinstance(data, dict):
        return base
    return {
        "active_tickers": _coerce_str_list(data.get("active_tickers")),
        "query_tickers": _coerce_str_list(data.get("query_tickers")),
        "compound_sources": _coerce_str_list(data.get("compound_sources")),
        "compound_tickers": _coerce_str_list(data.get("compound_tickers")),
    }


def thread_from_dict(data: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_thread_state()
    if not isinstance(data, dict):
        return base
    messages = data.get("messages")
    if not isinstance(messages, list):
        return base
    return ThreadState(messages=[dict(m) for m in messages if isinstance(m, dict)])


def memory_from_dict(data: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_memory_state()
    if not isinstance(data, dict):
        return base
    snapshots = data.get("market_snapshots")
    if not isinstance(snapshots, dict):
        snapshots = {}
    else:
        snapshots = {
            str(k).upper(): str(v)
            for k, v in snapshots.items()
            if str(k).strip()
        }
    prefetch = data.get("prefetched_market_block")
    return {
        "market_snapshots": snapshots,
        "tool_results": _coerce_dict_list(data.get("tool_results")),
        "plans": _coerce_dict_list(data.get("plans")),
        "prefetched_market_block": _coerce_str(prefetch) if prefetch else None,
    }


def research_from_dict(data: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_research_state()
    if not isinstance(data, dict):
        return base
    query = data.get("query")
    scratchpad = data.get("scratchpad_path")
    return {
        "query": _coerce_str(query) if query else None,
        "scratchpad_path": _coerce_str(scratchpad) if scratchpad else None,
        "is_follow_up": _coerce_bool(data.get("is_follow_up"), base["is_follow_up"]),
        "prior_turn_count": _coerce_int(
            data.get("prior_turn_count"),
            base["prior_turn_count"],
        ),
    }


def output_from_dict(data: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_output_state()
    if not isinstance(data, dict):
        return base
    final_answer = data.get("final_answer")
    route = data.get("route")
    return {
        "final_answer": _coerce_str(final_answer) if final_answer else None,
        "route": _coerce_str(route) if route else None,
    }


def control_from_dict(data: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_control_state()
    if not isinstance(data, dict):
        return base
    return ControlState(
        graph_enabled=_coerce_bool(data.get("graph_enabled"), base["graph_enabled"]),
    )


def state_to_dict(state: RalliesState) -> dict[str, Any]:
    """Convert RalliesState to a JSON-serializable dict."""
    return {
        "session": dict(state["session"]),
        "input": dict(state["input"]),
        "entities": dict(state["entities"]),
        "thread": {"messages": list(state["thread"]["messages"])},
        "memory": {
            "market_snapshots": dict(state["memory"]["market_snapshots"]),
            "tool_results": list(state["memory"]["tool_results"]),
            "plans": list(state["memory"]["plans"]),
            "prefetched_market_block": state["memory"]["prefetched_market_block"],
        },
        "research": dict(state["research"]),
        "output": dict(state["output"]),
        "control": dict(state["control"]),
    }


def state_from_dict(data: dict[str, Any] | None) -> RalliesState:
    """Rebuild RalliesState from a dict; missing keys use safe defaults."""
    if not isinstance(data, dict):
        return create_empty_state()
    return RalliesState(
        session=session_from_dict(data.get("session")),
        input=input_from_dict(data.get("input")),
        entities=entities_from_dict(data.get("entities")),
        thread=thread_from_dict(data.get("thread")),
        memory=memory_from_dict(data.get("memory")),
        research=research_from_dict(data.get("research")),
        output=output_from_dict(data.get("output")),
        control=control_from_dict(data.get("control")),
    )


def state_to_json(state: RalliesState, *, indent: int | None = None) -> str:
    return json.dumps(state_to_dict(state), ensure_ascii=True, indent=indent)


def state_from_json(text: str) -> RalliesState:
    payload = json.loads(text)
    return state_from_dict(payload)
