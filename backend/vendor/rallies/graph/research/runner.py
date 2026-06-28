"""Run /research via LangGraph subgraph."""

from __future__ import annotations

from typing import Any

from rallies.research.loop_steps import iteration_limit_answer

from ..flags import graph_checkpoints_enabled
from .config import build_research_invoke_config
from .context import ResearchGraphContext
from .graph_build import get_research_graph
from .messages import build_research_messages_with_memory
from .state import ResearchGraphState
from .state_slice import build_research_graph_context
from .tool_callback import attach_memory_callback_to_context


def build_initial_research_state(
    loop: Any,
    query: str,
    ctx: ResearchGraphContext,
) -> ResearchGraphState:
    if loop.session:
        loop.session.scratchpad.add_thinking(f"Research graph: {query[:200]}")
    messages = build_research_messages_with_memory(
        query,
        entities=ctx.entities_dict(),
        memory=ctx.memory_dict(),
    )
    return ResearchGraphState(
        query=query,
        messages=messages,
        iteration=0,
        max_iterations=loop.max_iterations,
        status="running",
        answer=None,
        pending_tool_calls=[],
        pending_done_answer=None,
        last_node="start",
    )


def extract_answer_from_final_state(final: ResearchGraphState, loop: Any) -> str:
    answer = final.get("answer")
    if answer and str(answer).strip():
        return str(answer).strip()
    if final.get("status") == "limit":
        return iteration_limit_answer(loop)
    return iteration_limit_answer(loop)


def run_research_graph(
    loop: Any,
    query: str,
    *,
    session_id: str | None = None,
    manager: Any | None = None,
    conversation: list[dict] | None = None,
) -> str:
    """Execute research through LangGraph nodes (checkpoint optional)."""
    graph = get_research_graph(use_checkpoint=graph_checkpoints_enabled())
    ctx = build_research_graph_context(
        loop,
        query,
        manager=manager,
        conversation=conversation,
    )
    attach_memory_callback_to_context(ctx)
    initial = build_initial_research_state(loop, query, ctx)
    config = build_research_invoke_config(
        session_id=session_id,
        ctx=ctx,
        use_checkpoint=graph_checkpoints_enabled(),
    )
    final = graph.invoke(initial, config)
    return extract_answer_from_final_state(final, loop)
