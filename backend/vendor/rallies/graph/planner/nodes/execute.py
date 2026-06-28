"""Planner execute node — run plan steps and summarize."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from rallies import console
from ..config import get_planner_context
from ..history import (
    print_plan_failure_footer,
    record_plan_step_completed as record_history_step_completed,
    record_plan_step_error,
    record_plan_step_failed_abort,
    record_plan_step_started,
)
from ..memory_write import record_plan_step_completed as record_memory_step_completed
from ..state import PlannerGraphState
from ..steps import execute_plan_steps


def planner_execute_node(
    state: PlannerGraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    ctx = get_planner_context(config)
    plan = list(state.get("plan") or [])
    round_num = int(state.get("round") or 1)
    max_rounds = int(state.get("max_rounds") or ctx.max_rounds)

    workspace, summaries, step_results, failed_item, error = execute_plan_steps(
        ctx.manager_agent(),
        ctx.prompt,
        plan,
        ctx.workspace,
    )
    ctx.workspace[:] = workspace

    if error:
        failed_title = None
        if isinstance(failed_item, dict):
            failed_title = str(failed_item.get("title") or "") or None
        record_plan_step_error(
            ctx.history_session(),
            title=failed_title or "planner_step",
            error=error,
        )
        record_plan_step_failed_abort(
            ctx.history_session(),
            error=error,
            step_title=failed_title,
        )
        console.print(error)
        console.print()
        print_plan_failure_footer(console)
        return {
            "status": "failed",
            "answer": "",
            "last_node": "planner_execute",
        }

    for index, item in enumerate(plan):
        result = step_results.get(str(index), "")
        summary = summaries.get(index, "")
        record_plan_step_started(
            ctx.history_session(),
            title=str(item.get("title") or ""),
            description=str(item.get("description") or ""),
        )
        record_history_step_completed(
            ctx.history_session(),
            title=str(item.get("title") or ""),
            description=str(item.get("description") or ""),
            result=str(result),
            summary=str(summary),
        )
        if ctx.memory_enabled:
            memory = ctx.memory_dict()
            ctx.rallies_state["memory"] = record_memory_step_completed(
                memory,
                title=str(item.get("title") or ""),
                description=str(item.get("description") or ""),
                result=str(result),
                summary=str(summary),
            )

    next_status = "answer" if round_num >= max_rounds else "plan"
    return {
        "plan": [],
        "status": next_status,
        "last_node": "planner_execute",
    }
