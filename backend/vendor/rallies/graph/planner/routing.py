"""Conditional edges for planner subgraph."""

from __future__ import annotations

from .state import PlannerGraphState


def route_after_plan(state: PlannerGraphState) -> str:
    status = str(state.get("status") or "")
    if status == "answer":
        return "planner_answer"
    return "planner_execute"


def route_after_execute(state: PlannerGraphState) -> str:
    status = str(state.get("status") or "")
    if status == "failed":
        return "planner_answer"
    if status == "plan":
        return "planner_plan"
    return "planner_answer"
