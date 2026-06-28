"""Bridge existing Manager / thread_memory objects into RalliesState (read-only)."""

from __future__ import annotations

from typing import Any

from ..thread_memory import ResolvedTurn, resolve_follow_up, session_messages
from ..ticker_identify import identify_query_tickers
from .defaults import (
    empty_control_state,
    empty_input_state,
    empty_memory_state,
    empty_output_state,
    empty_research_state,
    empty_session_state,
    empty_thread_state,
)
from .state import RalliesState


def _history_session_fields(history_session: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(history_session, dict):
        return {"id": "", "started_at": "", "file_path": ""}
    return {
        "id": str(history_session.get("id") or ""),
        "started_at": str(history_session.get("started_at") or ""),
        "file_path": str(history_session.get("file_path") or ""),
    }


def _compound_entity_fields(compound_context: Any) -> tuple[list[str], list[str]]:
    if compound_context is None:
        return [], []
    sources = list(getattr(compound_context, "sources", None) or [])
    tickers = list(getattr(compound_context, "tickers", None) or [])
    return [str(s) for s in sources], [str(t) for t in tickers]


def _research_fields(research_session: Any) -> dict[str, Any]:
    if research_session is None:
        return empty_research_state()
    query = getattr(research_session, "query", None)
    scratchpad_path = None
    filepath = getattr(research_session, "filepath", None)
    if filepath:
        scratchpad_path = str(filepath)
    return {
        "query": str(query) if query else None,
        "scratchpad_path": scratchpad_path,
        "is_follow_up": bool(getattr(research_session, "session_follow_up", False)),
        "prior_turn_count": 0,
    }


def _memory_from_research(research_session: Any) -> dict[str, Any]:
    memory = empty_memory_state()
    if research_session is None:
        return memory
    prefetch = getattr(research_session, "prefetched_market_block", None)
    if prefetch:
        memory["prefetched_market_block"] = str(prefetch)
    return memory


def entities_from_resolution(
    resolved: ResolvedTurn,
    *,
    compound_context: Any = None,
) -> dict[str, Any]:
    compound_sources, compound_tickers = _compound_entity_fields(compound_context)
    query_tickers = identify_query_tickers(resolved.raw_prompt)
    if not query_tickers:
        query_tickers = list(resolved.active_tickers)
    return {
        "active_tickers": list(resolved.active_tickers),
        "query_tickers": query_tickers,
        "compound_sources": compound_sources,
        "compound_tickers": compound_tickers,
    }


def state_from_turn(
    *,
    history_session: dict[str, Any] | None,
    prompt: str,
    conversation: list[dict],
    tier: str = "free",
    thread_max_tokens: int | None = None,
    resolved_turn: ResolvedTurn | None = None,
    research_session: Any = None,
    compound_context: Any = None,
    route: str | None = None,
) -> RalliesState:
    """Pack one in-flight turn into RalliesState without mutating rallies runtime."""
    session_id = str((history_session or {}).get("id") or "")
    resolved = resolved_turn or resolve_follow_up(
        conversation, prompt, session_id=session_id or None
    )
    hist = _history_session_fields(history_session)
    session = empty_session_state(
        session_id=hist["id"],
        started_at=hist["started_at"],
        file_path=hist["file_path"],
        tier=tier,
        thread_max_tokens=thread_max_tokens,
    )
    research = _research_fields(research_session)
    research["is_follow_up"] = resolved.is_follow_up
    research["prior_turn_count"] = resolved.prior_turn_count
    if research["query"] is None:
        research["query"] = resolved.raw_prompt

    return RalliesState(
        session=session,
        input=empty_input_state(
            raw_prompt=resolved.raw_prompt,
            effective_prompt=resolved.effective_prompt,
        ),
        entities=entities_from_resolution(resolved, compound_context=compound_context),
        thread=empty_thread_state(
            messages=session_messages(conversation, session_id=session_id or None)
        ),
        memory=_memory_from_research(research_session),
        research=research,
        output=empty_output_state() if route is None else {"final_answer": None, "route": route},
        control=empty_control_state(),
    )


def state_from_manager(
    manager: Any,
    prompt: str,
    conversation: list[dict],
    *,
    route: str | None = None,
) -> RalliesState:
    """
    Snapshot Manager fields into RalliesState.

    Does not call begin_research_session or mutate manager state.
    """
    history_session = getattr(manager, "history_session", None)
    tier = str(getattr(manager, "tier", "free"))
    thread_max_tokens = getattr(manager, "thread_max_tokens", None)
    resolved = getattr(manager, "_resolved_turn", None)
    if resolved is None:
        session_id = str((history_session or {}).get("id") or "")
        resolved = resolve_follow_up(
            conversation, prompt, session_id=session_id or None
        )
    research_session = getattr(manager, "research_session", None)
    compound_context = getattr(manager, "compound_context", None)

    return state_from_turn(
        history_session=history_session,
        prompt=prompt,
        conversation=conversation,
        tier=tier,
        thread_max_tokens=thread_max_tokens,
        resolved_turn=resolved,
        research_session=research_session,
        compound_context=compound_context,
        route=route,
    )


def state_from_conversation(
    prompt: str,
    conversation: list[dict],
    *,
    thread_max_tokens: int | None = None,
) -> RalliesState:
    """Lightweight bridge when no Manager instance is available (tests)."""
    return state_from_turn(
        history_session=None,
        prompt=prompt,
        conversation=conversation,
        thread_max_tokens=thread_max_tokens,
    )
