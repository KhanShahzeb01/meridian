"""Build LLM message lists from unified RalliesState."""

from __future__ import annotations

from typing import Any

from .state import RalliesState


def build_planner_messages(state: RalliesState) -> list[dict[str, Any]]:
    """
    Mirror thread_memory.new_turn_workspace / build_thread_context.

    Uses the REPL conversation in state.thread.messages plus input prompts.
    """
    from ..thread_memory import build_thread_context

    return build_thread_context(
        state["thread"]["messages"],
        raw_prompt=state["input"]["raw_prompt"],
        effective_prompt=state["input"]["effective_prompt"],
        max_tokens=state["session"]["thread_max_tokens"],
        session_id=str(state["session"].get("id") or "") or None,
    )


def prefetch_compare_message(state: RalliesState) -> dict[str, Any] | None:
    """Optional compare prefetch block (same shape Manager uses at answer time)."""
    from ..thread_memory import should_inject_compare_prefetch

    block = state["memory"].get("prefetched_market_block")
    tickers = state["entities"].get("query_tickers") or []
    if not block:
        return None
    raw_prompt = str(state["input"].get("raw_prompt") or "")
    is_follow_up = bool(state["research"].get("is_follow_up"))
    if should_inject_compare_prefetch(raw_prompt=raw_prompt, is_follow_up=is_follow_up):
        if len(tickers) < 2:
            return None
        content = (
            f"{block}\n\n"
            "Instruction: Write a complete side-by-side comparison "
            f"for {', '.join(tickers)} using the data above. "
            "Do not ask the user to retrieve missing tickers."
        )
    else:
        content = (
            f"{block}\n\n"
            "Instruction: Use the prefetched market data above when "
            "answering the user's latest question."
        )
    return {"role": "user", "content": content, "type": "data"}


def build_memory_digest_message(state: RalliesState) -> dict[str, Any] | None:
    """Optional system message with structured session memory."""
    from .flags import graph_memory_enabled
    from .memory.digest import memory_digest

    if not graph_memory_enabled():
        return None
    digest = memory_digest(state)
    if not digest.strip():
        return None
    return {"role": "system", "content": digest}


def build_llm_context(
    state: RalliesState,
    *,
    include_prefetch: bool = False,
    include_memory_digest: bool = False,
) -> list[dict[str, Any]]:
    """
    Messages for planner / answer LLM calls.

    Phase 0: delegates thread trimming to existing thread_memory helpers.
    Phase 4: optional memory digest when include_memory_digest=True and flag on.
    """
    messages = build_planner_messages(state)
    if include_memory_digest:
        digest_message = build_memory_digest_message(state)
        if digest_message:
            messages = list(messages)
            messages.insert(0, digest_message)
    if include_prefetch:
        prefetch = prefetch_compare_message(state)
        if prefetch:
            messages = list(messages)
            messages.append(prefetch)
    return messages
