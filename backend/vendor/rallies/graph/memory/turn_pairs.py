"""User query + final answer pairs — the only cross-turn memory we persist."""

from __future__ import annotations

from typing import Any, TypedDict

from ...helpers import TokenCounter


class TurnPair(TypedDict):
    user_query: str
    assistant_answer: str


def normalize_turn_pair(
    user_query: str,
    assistant_answer: str,
) -> TurnPair | None:
    user = str(user_query or "").strip()
    answer = str(assistant_answer or "").strip()
    if not user or not answer:
        return None
    return TurnPair(user_query=user, assistant_answer=answer)


def pairs_to_thread_messages(pairs: list[TurnPair] | list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convert stored pairs to clean user/assistant messages for LLM context."""
    messages: list[dict[str, str]] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        user = str(pair.get("user_query") or "").strip()
        answer = str(pair.get("assistant_answer") or "").strip()
        if user:
            messages.append({"role": "user", "content": user})
        if answer:
            messages.append({"role": "assistant", "content": answer})
    return messages


def trim_turn_pairs_to_budget(
    pairs: list[TurnPair] | list[dict[str, Any]],
    max_tokens: int,
) -> list[dict[str, Any]]:
    """Drop oldest query/answer pairs until the thread fits the token budget."""
    counter = TokenCounter()
    trimmed = pairs_to_thread_messages(pairs)
    while len(trimmed) > 2 and counter.count_conversation_tokens(trimmed) > max_tokens:
        trimmed.pop(0)
        if trimmed and trimmed[0].get("role") == "assistant":
            trimmed.pop(0)
    rebuilt: list[dict[str, Any]] = []
    idx = 0
    while idx < len(trimmed):
        if trimmed[idx].get("role") != "user":
            idx += 1
            continue
        user = str(trimmed[idx].get("content") or "")
        answer = ""
        if idx + 1 < len(trimmed) and trimmed[idx + 1].get("role") == "assistant":
            answer = str(trimmed[idx + 1].get("content") or "")
            idx += 2
        else:
            idx += 1
        pair = normalize_turn_pair(user, answer)
        if pair:
            rebuilt.append(dict(pair))
    return rebuilt
