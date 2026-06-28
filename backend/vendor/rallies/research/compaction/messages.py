"""Message helpers for full compaction in the research loop."""

from __future__ import annotations

from .constants import MIN_TOOL_RESULTS_FOR_COMPACTION
from ..microcompact import MC_CLEARED_MESSAGE


def estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def estimate_messages_tokens(messages: list[dict]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content") or ""
        if isinstance(content, str):
            total += estimate_tokens(content)
        else:
            total += estimate_tokens(str(content))
    return total


def count_active_tool_messages(messages: list[dict]) -> int:
    count = 0
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        content = msg.get("content") or ""
        if isinstance(content, str) and content and content != MC_CLEARED_MESSAGE:
            count += 1
    return count


def collect_tool_results_text(messages: list[dict]) -> str:
    blocks: list[str] = []
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        content = msg.get("content") or ""
        if not isinstance(content, str) or not content or content == MC_CLEARED_MESSAGE:
            continue
        name = msg.get("name") or "tool"
        blocks.append(f"### {name}\n{content}")
    return "\n\n".join(blocks)


def should_run_full_compaction(
    messages: list[dict],
    *,
    token_threshold: int,
    tool_count_threshold: int,
) -> bool:
    tool_count = count_active_tool_messages(messages)
    if tool_count < MIN_TOOL_RESULTS_FOR_COMPACTION:
        return False
    tokens = estimate_messages_tokens(messages)
    if tokens >= token_threshold:
        return True
    return tool_count >= tool_count_threshold


def apply_compaction_to_messages(messages: list[dict], summary: str) -> list[dict]:
    """Replace history with system + user(query + summary) — Dexter-style."""
    system_msgs = [m for m in messages if m.get("role") == "system"]
    original_query = _first_user_content(messages)
    combined = f"{original_query}\n\n{summary}".strip()
    return system_msgs + [{"role": "user", "content": combined}]


def _first_user_content(messages: list[dict]) -> str:
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content") or ""
            if isinstance(content, str):
                return content
    return ""
