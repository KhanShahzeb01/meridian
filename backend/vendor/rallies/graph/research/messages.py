"""Research LLM messages with optional session memory digest."""

from __future__ import annotations

from typing import Any

from rallies.research.loop_steps import build_initial_messages

from ..flags import graph_memory_enabled
from ..memory.digest import memory_digest_from_slice
from ..memory.marker import is_session_memory_message


def strip_session_memory_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [msg for msg in messages if not is_session_memory_message(msg)]


def _insert_after_first_system(
    messages: list[dict[str, Any]],
    insert_message: dict[str, Any],
) -> list[dict[str, Any]]:
    for index, message in enumerate(messages):
        if message.get("role") == "system":
            return messages[: index + 1] + [insert_message] + messages[index + 1 :]
    return [insert_message] + messages


def build_session_memory_message(digest: str) -> dict[str, str]:
    return {"role": "system", "content": digest}


def apply_session_memory_digest(
    messages: list[dict[str, Any]],
    *,
    entities: dict[str, Any],
    memory: dict[str, Any],
) -> list[dict[str, Any]]:
    """Refresh session memory block before an LLM call (graph research path)."""
    if not graph_memory_enabled():
        return messages

    digest = memory_digest_from_slice({"entities": entities, "memory": memory})
    cleaned = strip_session_memory_messages(list(messages))
    if not digest.strip():
        return cleaned

    memory_message = build_session_memory_message(digest)
    return _insert_after_first_system(cleaned, memory_message)


def build_research_messages_with_memory(
    query: str,
    *,
    entities: dict[str, Any],
    memory: dict[str, Any],
) -> list[dict[str, Any]]:
    """Initial /research messages with optional memory digest."""
    messages = build_initial_messages(query)
    return apply_session_memory_digest(
        messages,
        entities=entities,
        memory=memory,
    )
