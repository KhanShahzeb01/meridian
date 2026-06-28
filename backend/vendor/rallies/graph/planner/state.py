"""Typed state for the planner LangGraph subgraph."""

from __future__ import annotations

from typing import Any, TypedDict


class PlannerGraphState(TypedDict):
    round: int
    max_rounds: int
    max_steps_per_round: int
    plan: list[dict[str, Any]]
    status: str
    answer: str | None
    last_node: str
