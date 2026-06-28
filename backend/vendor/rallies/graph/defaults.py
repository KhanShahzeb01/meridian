"""Factory helpers for empty or partial RalliesState values."""

from __future__ import annotations

from .state import (
    ControlState,
    EntitiesState,
    InputState,
    MemoryState,
    OutputState,
    RalliesState,
    ResearchState,
    SessionState,
    ThreadState,
)


def default_thread_max_tokens() -> int:
    from ..token_budgets import default_thread_token_budget

    return default_thread_token_budget()


def empty_session_state(
    *,
    session_id: str = "",
    started_at: str = "",
    file_path: str = "",
    tier: str = "free",
    thread_max_tokens: int | None = None,
) -> SessionState:
    cap = thread_max_tokens if thread_max_tokens is not None else default_thread_max_tokens()
    return SessionState(
        id=session_id,
        started_at=started_at,
        file_path=file_path,
        tier=tier,
        thread_max_tokens=cap,
    )


def empty_input_state(*, raw_prompt: str = "", effective_prompt: str = "") -> InputState:
    raw = raw_prompt.strip()
    effective = effective_prompt.strip() or raw
    return InputState(raw_prompt=raw, effective_prompt=effective)


def empty_entities_state() -> EntitiesState:
    return EntitiesState(
        active_tickers=[],
        query_tickers=[],
        compound_sources=[],
        compound_tickers=[],
    )


def empty_thread_state(*, messages: list[dict] | None = None) -> ThreadState:
    return ThreadState(messages=list(messages or []))


def empty_memory_state() -> MemoryState:
    return MemoryState(
        market_snapshots={},
        tool_results=[],
        plans=[],
        prefetched_market_block=None,
    )


def empty_research_state() -> ResearchState:
    return ResearchState(
        query=None,
        scratchpad_path=None,
        is_follow_up=False,
        prior_turn_count=0,
    )


def empty_output_state() -> OutputState:
    return OutputState(final_answer=None, route=None)


def empty_control_state(*, graph_enabled: bool = False) -> ControlState:
    return ControlState(graph_enabled=graph_enabled)


def create_empty_state(
    *,
    session: SessionState | None = None,
    raw_prompt: str = "",
    effective_prompt: str = "",
    conversation: list[dict] | None = None,
) -> RalliesState:
    """Minimal valid state for tests and future graph bootstrap."""
    return RalliesState(
        session=session or empty_session_state(),
        input=empty_input_state(raw_prompt=raw_prompt, effective_prompt=effective_prompt),
        entities=empty_entities_state(),
        thread=empty_thread_state(messages=conversation),
        memory=empty_memory_state(),
        research=empty_research_state(),
        output=empty_output_state(),
        control=empty_control_state(),
    )
