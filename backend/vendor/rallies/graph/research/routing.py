"""Conditional routing for research subgraph."""

from __future__ import annotations

from typing import Literal

from .state import ResearchGraphState

RouteTarget = Literal["research_tools", "research_done", "research_decide"]


def route_after_decide(state: ResearchGraphState) -> RouteTarget:
    status = state.get("status") or "running"
    if status in ("done", "limit", "parse_error"):
        return "research_done"
    if state.get("pending_tool_calls"):
        return "research_tools"
    return "research_decide"


def should_continue_iterations(state: ResearchGraphState) -> bool:
    status = state.get("status") or "running"
    if status != "running":
        return False
    iteration = int(state.get("iteration") or 0)
    max_iterations = int(state.get("max_iterations") or 1)
    return iteration < max_iterations
