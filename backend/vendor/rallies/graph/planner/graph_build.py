"""Compile the planner LangGraph subgraph."""

from __future__ import annotations

from typing import Any

from .nodes import planner_answer_node, planner_execute_node, planner_plan_node
from .routing import route_after_execute, route_after_plan
from .state import PlannerGraphState

_compiled_planner_graph: Any | None = None
_compiled_with_checkpoint: bool | None = None


def _build_planner_graph(*, use_checkpoint: bool):
    from langgraph.graph import END, StateGraph

    from ..checkpoint_store import get_checkpointer
    from ..flags import graph_checkpoints_enabled, langgraph_available

    builder = StateGraph(PlannerGraphState)
    builder.add_node("planner_plan", planner_plan_node)
    builder.add_node("planner_execute", planner_execute_node)
    builder.add_node("planner_answer", planner_answer_node)
    builder.set_entry_point("planner_plan")

    builder.add_conditional_edges(
        "planner_plan",
        route_after_plan,
        {
            "planner_execute": "planner_execute",
            "planner_answer": "planner_answer",
        },
    )
    builder.add_conditional_edges(
        "planner_execute",
        route_after_execute,
        {
            "planner_plan": "planner_plan",
            "planner_answer": "planner_answer",
        },
    )
    builder.add_edge("planner_answer", END)

    checkpointer = None
    if use_checkpoint and graph_checkpoints_enabled() and langgraph_available():
        checkpointer = get_checkpointer()
    return builder.compile(checkpointer=checkpointer)


def get_planner_graph(*, use_checkpoint: bool = True):
    """Return compiled planner subgraph (cached)."""
    global _compiled_planner_graph, _compiled_with_checkpoint
    if _compiled_planner_graph is None or _compiled_with_checkpoint != use_checkpoint:
        _compiled_planner_graph = _build_planner_graph(use_checkpoint=use_checkpoint)
        _compiled_with_checkpoint = use_checkpoint
    return _compiled_planner_graph


def reset_planner_graph_cache() -> None:
    """Test helper."""
    global _compiled_planner_graph, _compiled_with_checkpoint
    _compiled_planner_graph = None
    _compiled_with_checkpoint = None
