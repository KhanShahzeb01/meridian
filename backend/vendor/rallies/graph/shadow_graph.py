"""Minimal shadow graph: ingest_input → persist_turn (checkpoint only)."""

from __future__ import annotations

from typing import Any

from .checkpoint_store import get_checkpointer
from .langgraph_state import ShadowGraphState
from .nodes import ingest_input_node, persist_turn_node

_compiled_graph: Any | None = None


def _build_shadow_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(ShadowGraphState)
    builder.add_node("ingest_input", ingest_input_node)
    builder.add_node("persist_turn", persist_turn_node)
    builder.set_entry_point("ingest_input")
    builder.add_edge("ingest_input", "persist_turn")
    builder.add_edge("persist_turn", END)
    return builder.compile(checkpointer=get_checkpointer())


def get_shadow_graph():
    """Compiled shadow graph with SqliteSaver checkpointer."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_shadow_graph()
    return _compiled_graph


def reset_shadow_graph_cache() -> None:
    """Test helper — force graph recompile on next use."""
    global _compiled_graph
    _compiled_graph = None
