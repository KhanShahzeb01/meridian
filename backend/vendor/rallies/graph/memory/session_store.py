"""Session store for query/answer turn pairs — backed by .rallies/memory/*.json."""

from __future__ import annotations

from ...memory.file_store import (
    append_session_turn,
    clear_session_memory_file,
    load_session_llm_messages,
)
from .turn_pairs import TurnPair, normalize_turn_pair

TURN_MEMORY_THREAD_PREFIX = "turns:"


def reset_turn_memory_graph_cache() -> None:
    """No-op: file-backed memory has no graph cache. Kept for test compatibility."""


def turn_memory_thread_id(session_id: str) -> str:
    return f"{TURN_MEMORY_THREAD_PREFIX}{session_id}"


def turn_memory_config(session_id: str) -> dict[str, dict[str, str]]:
    from ..checkpoint import thread_checkpoint_config

    return thread_checkpoint_config(turn_memory_thread_id(session_id))


def load_turn_pairs(session_id: str) -> list[TurnPair]:
    """Load persisted user-query / final-answer pairs for a session."""
    session_id = str(session_id or "").strip()
    if not session_id:
        return []
    messages = load_session_llm_messages(session_id)
    pairs: list[TurnPair] = []
    idx = 0
    while idx < len(messages):
        if messages[idx].get("role") != "user":
            idx += 1
            continue
        user = str(messages[idx].get("content") or "")
        answer = ""
        if idx + 1 < len(messages) and messages[idx + 1].get("role") == "assistant":
            answer = str(messages[idx + 1].get("content") or "")
            idx += 2
        else:
            idx += 1
        pair = normalize_turn_pair(user, answer)
        if pair:
            pairs.append(pair)
    return pairs


def append_turn_pair(
    session_id: str,
    user_query: str,
    assistant_answer: str,
) -> TurnPair | None:
    """Append one completed turn. Planner steps are never stored."""
    pair = normalize_turn_pair(user_query, assistant_answer)
    if pair is None:
        return None
    append_session_turn(session_id, pair["user_query"], pair["assistant_answer"])
    return pair


def clear_turn_pairs(session_id: str) -> None:
    """Remove all turn pairs for a session (/clear)."""
    clear_session_memory_file(session_id)
