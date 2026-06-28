"""Planner plan node — one LLM planning round."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from ....thread_memory import messages_for_planner
from ..history import record_plan_generated
from ..memory_write import record_plan_generated as record_plan_memory
from ..messages import build_planner_input_messages
from ..state import PlannerGraphState
from ..steps import cap_plan
from ..config import get_planner_context


def planner_plan_node(
    state: PlannerGraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    ctx = get_planner_context(config)
    round_num = int(state.get("round") or 0) + 1
    max_rounds = int(state.get("max_rounds") or ctx.max_rounds)
    max_steps = int(state.get("max_steps_per_round") or ctx.max_steps_per_round)

    resolved = getattr(ctx.manager, "_resolved_turn", None)
    prior_cmd = resolved.prior_command if resolved else None
    planner_messages = build_planner_input_messages(
        messages_for_planner(
            ctx.workspace,
            ctx.prompt,
            prior_command=prior_cmd,
        ),
        ctx.rallies_state,
        include_memory_digest=ctx.memory_enabled,
    )
    plan = ctx.manager_agent().run(planner_messages, max_steps=max_steps)
    plan = cap_plan(plan, max_steps)

    record_plan_generated(
        ctx.history_session(),
        plan=plan,
        round_num=round_num,
        max_rounds=max_rounds,
    )
    if ctx.memory_enabled:
        memory = ctx.memory_dict()
        ctx.rallies_state["memory"] = record_plan_memory(
            memory,
            round_num=round_num,
            plan=plan,
        )

    if not plan:
        return {
            "round": round_num,
            "plan": [],
            "status": "answer",
            "last_node": "planner_plan",
        }

    ctx.workspace.append({"role": "assistant", "content": str(plan)})
    return {
        "round": round_num,
        "plan": plan,
        "status": "execute",
        "last_node": "planner_plan",
    }
