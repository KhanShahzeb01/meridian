"""Save and load shadow-graph checkpoints per rallies history session."""

from __future__ import annotations

from typing import Any

from .bridge import state_from_manager
from .checkpoint import thread_checkpoint_config
from .flags import graph_checkpoints_enabled, langgraph_available
from .serializers import state_from_dict, state_to_dict
from .shadow_graph import get_shadow_graph
from .state import RalliesState


def _route_for_prompt(prompt: str, *, simple_ticker: bool = False) -> str:
    if simple_ticker:
        return "simple_ticker"
    return "planner"


def build_turn_rallies_state(
    manager: Any,
    prompt: str,
    conversation: list[dict],
    *,
    answer: str = "",
    simple_ticker: bool = False,
) -> RalliesState:
    """Snapshot Manager into RalliesState at end of a turn."""
    state = state_from_manager(
        manager,
        prompt,
        conversation,
        route=_route_for_prompt(prompt, simple_ticker=simple_ticker),
    )
    state["control"]["graph_enabled"] = graph_checkpoints_enabled()
    if answer:
        state["output"]["final_answer"] = str(answer)
    return state


def rallies_state_to_shadow_input(state: RalliesState) -> dict[str, Any]:
    return {"rallies": state_to_dict(state), "last_node": ""}


def save_turn_checkpoint(
    manager: Any,
    prompt: str,
    conversation: list[dict],
    *,
    answer: str = "",
    simple_ticker: bool = False,
) -> RalliesState | None:
    """
    Run shadow graph for one turn and persist checkpoint.

    Returns the rallies state written, or None when skipped/failed.
    """
    if not graph_checkpoints_enabled():
        return None
    if not langgraph_available():
        return None

    history_session = getattr(manager, "history_session", None)
    session_id = str((history_session or {}).get("id") or "").strip()
    if not session_id:
        return None

    rallies_state = build_turn_rallies_state(
        manager,
        prompt,
        conversation,
        answer=answer,
        simple_ticker=simple_ticker,
    )
    graph = get_shadow_graph()
    config = thread_checkpoint_config(session_id)
    graph.invoke(rallies_state_to_shadow_input(rallies_state), config)
    return rallies_state


def load_shadow_graph_values(session_id: str) -> dict[str, Any] | None:
    """Load raw shadow graph values for a thread_id (dev / status)."""
    if not session_id or not langgraph_available():
        return None
    graph = get_shadow_graph()
    config = thread_checkpoint_config(session_id)
    snapshot = graph.get_state(config)
    if snapshot is None:
        return None
    values = getattr(snapshot, "values", None)
    if not isinstance(values, dict):
        return None
    if not values.get("rallies"):
        return None
    return values


def load_checkpoint_rallies_state(session_id: str) -> RalliesState | None:
    """Rebuild RalliesState from the latest checkpoint for a session."""
    values = load_shadow_graph_values(session_id)
    if not values:
        return None
    rallies = values.get("rallies")
    if not isinstance(rallies, dict):
        return None
    return state_from_dict(rallies)
