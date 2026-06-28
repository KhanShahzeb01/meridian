"""Per-turn lightweight trim of old tool results (Wave 3 rank 11)."""

from __future__ import annotations

from dataclasses import dataclass

MC_CLEARED_MESSAGE = "[Old tool result content cleared]"

COUNT_TRIGGER_THRESHOLD = 8
COUNT_KEEP_RECENT = 4
TOKEN_TRIGGER_THRESHOLD = 80_000

COMPACTABLE_ROLES = frozenset({"tool"})


@dataclass(frozen=True)
class MicrocompactResult:
    messages: list[dict]
    cleared: int
    estimated_tokens_saved: int
    trigger: str | None


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def microcompact_messages(messages: list[dict]) -> MicrocompactResult:
    """
    Trim old tool-role message bodies in the research loop message list.

    Only applies to messages with role=tool (OpenAI-style tool results).
    """
    compactable_indices: list[int] = []
    for i, msg in enumerate(messages):
        if msg.get("role") not in COMPACTABLE_ROLES:
            continue
        content = msg.get("content") or ""
        if isinstance(content, str) and content and content != MC_CLEARED_MESSAGE:
            compactable_indices.append(i)

    count_triggered = len(compactable_indices) > COUNT_TRIGGER_THRESHOLD
    total_tokens = 0
    if not count_triggered:
        for idx in compactable_indices:
            content = messages[idx].get("content") or ""
            if isinstance(content, str):
                total_tokens += _estimate_tokens(content)
    token_triggered = not count_triggered and total_tokens > TOKEN_TRIGGER_THRESHOLD

    if not count_triggered and not token_triggered:
        return MicrocompactResult(messages=messages, cleared=0, estimated_tokens_saved=0, trigger=None)

    keep_set = set(compactable_indices[-COUNT_KEEP_RECENT:])
    clear_indices = [i for i in compactable_indices if i not in keep_set]
    if not clear_indices:
        return MicrocompactResult(messages=messages, cleared=0, estimated_tokens_saved=0, trigger=None)

    tokens_saved = 0
    clear_set = set(clear_indices)
    new_messages: list[dict] = []
    for i, msg in enumerate(messages):
        if i in clear_set:
            content = msg.get("content") or ""
            if isinstance(content, str):
                tokens_saved += _estimate_tokens(content)
            new_messages.append({**msg, "content": MC_CLEARED_MESSAGE})
        else:
            new_messages.append(msg)

    trigger = "count" if count_triggered else "token"
    return MicrocompactResult(
        messages=new_messages,
        cleared=len(clear_indices),
        estimated_tokens_saved=tokens_saved,
        trigger=trigger,
    )
