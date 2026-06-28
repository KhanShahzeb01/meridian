"""Planner answer node — stream final response."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from ..config import get_planner_context
from ..state import PlannerGraphState


def planner_answer_node(
    state: PlannerGraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    ctx = get_planner_context(config)
    if state.get("status") == "failed":
        return {
            "answer": "",
            "status": "done",
            "last_node": "planner_answer",
        }
    answer = ctx.manager._stream_final_answer(ctx.prompt, ctx.workspace, ctx.thread)
    return {
        "answer": answer,
        "status": "done",
        "last_node": "planner_answer",
    }
