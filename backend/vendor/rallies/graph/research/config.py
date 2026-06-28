"""LangGraph configurable keys for research subgraph."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from ..checkpoint import thread_checkpoint_config
from .context import ResearchGraphContext

RESEARCH_CTX_KEY = "research_ctx"


def research_thread_id(session_id: str) -> str:
    """Distinct checkpoint thread for /research iterations."""
    return f"{session_id}:research"


def build_research_invoke_config(
    *,
    session_id: str | None,
    ctx: ResearchGraphContext,
    use_checkpoint: bool,
) -> dict[str, Any]:
    config: dict[str, Any] = {"configurable": {RESEARCH_CTX_KEY: ctx}}
    if use_checkpoint and session_id:
        base = thread_checkpoint_config(research_thread_id(session_id))
        config["configurable"].update(base["configurable"])
    return config


def get_research_context(config: RunnableConfig | dict[str, Any] | None) -> ResearchGraphContext:
    if not config:
        raise ValueError("research graph config missing")
    configurable = config.get("configurable") or {}
    ctx = configurable.get(RESEARCH_CTX_KEY)
    if not isinstance(ctx, ResearchGraphContext):
        raise ValueError("research_ctx not found in graph config")
    return ctx
