"""Serializable state for the /research LangGraph subgraph."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

ResearchStatus = Literal["running", "done", "limit", "parse_error"]


class ResearchGraphState(TypedDict, total=False):
    query: str
    messages: list[dict[str, Any]]
    iteration: int
    max_iterations: int
    status: ResearchStatus
    answer: str | None
    pending_tool_calls: list[dict[str, Any]]
    pending_done_answer: str | None
    last_node: str
