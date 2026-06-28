"""Research decide node — one LLM planning iteration."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from rallies.research.loop_steps import (
    DecideOutcome,
    append_format_nudge,
    append_must_use_tools_nudge,
    apply_microcompact,
    finalize_done_answer,
    iteration_limit_answer,
    parse_error_fallback,
    run_llm_decide,
)
from ..config import get_research_context
from ..messages import apply_session_memory_digest
from ..state import ResearchGraphState


def _iteration_limit_state(loop: Any, iteration: int, messages: list[dict]) -> dict[str, Any]:
    return {
        "messages": messages,
        "iteration": iteration,
        "status": "limit",
        "answer": iteration_limit_answer(loop),
        "pending_tool_calls": [],
        "pending_done_answer": None,
        "last_node": "research_decide",
    }


def _parse_error_state(
    outcome: DecideOutcome,
    iteration: int,
    messages: list[dict],
) -> dict[str, Any]:
    return {
        "messages": messages,
        "iteration": iteration,
        "status": "parse_error",
        "answer": parse_error_fallback(outcome),
        "pending_tool_calls": [],
        "pending_done_answer": None,
        "last_node": "research_decide",
    }


def _tool_calls_state(
    outcome: DecideOutcome,
    iteration: int,
    messages: list[dict],
) -> dict[str, Any]:
    return {
        "messages": messages,
        "iteration": iteration,
        "status": "running",
        "pending_tool_calls": outcome.all_tool_calls,
        "pending_done_answer": outcome.done_answer,
        "last_node": "research_decide",
    }


def _done_state(answer: str, iteration: int, messages: list[dict]) -> dict[str, Any]:
    return {
        "messages": messages,
        "iteration": iteration,
        "status": "done",
        "answer": answer,
        "pending_tool_calls": [],
        "pending_done_answer": None,
        "last_node": "research_decide",
    }


def research_decide_node(
    state: ResearchGraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    ctx = get_research_context(config)
    loop = ctx.loop
    iteration = int(state.get("iteration") or 0) + 1
    max_iterations = int(state.get("max_iterations") or loop.max_iterations)
    messages = list(state.get("messages") or [])

    if iteration > max_iterations:
        return _iteration_limit_state(loop, iteration, messages)

    if loop.progress is not None:
        loop.progress.iteration(iteration, max_iterations)

    messages = apply_microcompact(
        messages,
        session=loop.session,
        progress=loop.progress,
    )
    messages = loop._maybe_full_compact(messages, str(state.get("query") or ""))
    messages = apply_session_memory_digest(
        messages,
        entities=ctx.entities_dict(),
        memory=ctx.memory_dict(),
    )

    outcome = run_llm_decide(loop, messages, iteration=iteration)
    if outcome.parse_error:
        return _parse_error_state(outcome, iteration, messages)

    if outcome.all_tool_calls:
        return _tool_calls_state(outcome, iteration, messages)

    if outcome.done_answer:
        if loop.executor.tool_call_count == 0:
            append_must_use_tools_nudge(messages)
            return {
                "messages": messages,
                "iteration": iteration,
                "status": "running",
                "pending_tool_calls": [],
                "pending_done_answer": None,
                "last_node": "research_decide",
            }
        answer = finalize_done_answer(loop, outcome.done_answer, iteration=iteration)
        return _done_state(answer, iteration, messages)

    if outcome.thinking and loop.session:
        loop.session.scratchpad.add_thinking(
            f"Non-JSON research response (retrying): {outcome.raw[:400]}"
        )

    append_format_nudge(messages)
    return {
        "messages": messages,
        "iteration": iteration,
        "status": "running",
        "pending_tool_calls": [],
        "pending_done_answer": None,
        "last_node": "research_decide",
    }
