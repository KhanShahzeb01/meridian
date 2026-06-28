"""LangGraph configurable keys for planner subgraph."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from ..checkpoint import thread_checkpoint_config
from .context import PlannerGraphContext

PLANNER_CTX_KEY = "planner_ctx"


def planner_thread_id(session_id: str) -> str:
    """Distinct checkpoint thread for planner rounds."""
    return f"{session_id}:planner"


def build_planner_invoke_config(
    *,
    session_id: str | None,
    ctx: PlannerGraphContext,
    use_checkpoint: bool,
) -> dict[str, Any]:
    config: dict[str, Any] = {"configurable": {PLANNER_CTX_KEY: ctx}}
    if use_checkpoint and session_id:
        base = thread_checkpoint_config(planner_thread_id(session_id))
        config["configurable"].update(base["configurable"])
    return config


def get_planner_context(config: RunnableConfig | dict[str, Any] | None) -> PlannerGraphContext:
    if not config:
        raise ValueError("planner graph config missing")
    configurable = config.get("configurable") or {}
    ctx = configurable.get(PLANNER_CTX_KEY)
    if not isinstance(ctx, PlannerGraphContext):
        raise ValueError("planner_ctx not found in graph config")
    return ctx
