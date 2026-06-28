"""Compile the /research LangGraph subgraph."""

from __future__ import annotations

from typing import Any

from .nodes import research_decide_node, research_done_node, research_tools_node
from .routing import route_after_decide
from .state import ResearchGraphState

_compiled_research_graph: Any | None = None
_compiled_with_checkpoint: bool | None = None


def _build_research_graph(*, use_checkpoint: bool):
    from langgraph.graph import END, StateGraph

    from ..checkpoint_store import get_checkpointer
    from ..flags import graph_checkpoints_enabled, langgraph_available

    builder = StateGraph(ResearchGraphState)
    builder.add_node("research_decide", research_decide_node)
    builder.add_node("research_tools", research_tools_node)
    builder.add_node("research_done", research_done_node)
    builder.set_entry_point("research_decide")

    builder.add_conditional_edges(
        "research_decide",
        route_after_decide,
        {
            "research_tools": "research_tools",
            "research_done": "research_done",
            "research_decide": "research_decide",
        },
    )
    builder.add_edge("research_tools", "research_decide")
    builder.add_edge("research_done", END)

    checkpointer = None
    if use_checkpoint and graph_checkpoints_enabled() and langgraph_available():
        checkpointer = get_checkpointer()
    return builder.compile(checkpointer=checkpointer)


def get_research_graph(*, use_checkpoint: bool = True):
    """Return compiled research subgraph (cached)."""
    global _compiled_research_graph, _compiled_with_checkpoint
    if _compiled_research_graph is None or _compiled_with_checkpoint != use_checkpoint:
        _compiled_research_graph = _build_research_graph(use_checkpoint=use_checkpoint)
        _compiled_with_checkpoint = use_checkpoint
    return _compiled_research_graph


def reset_research_graph_cache() -> None:
    """Test helper."""
    global _compiled_research_graph, _compiled_with_checkpoint
    _compiled_research_graph = None
    _compiled_with_checkpoint = None
