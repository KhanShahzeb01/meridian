"""Markers for session memory messages in LLM context."""

from __future__ import annotations

from typing import Any

SESSION_MEMORY_MARKER = "## Session memory (rallies)"


def is_session_memory_message(message: dict[str, Any]) -> bool:
    if message.get("role") != "system":
        return False
    content = str(message.get("content") or "")
    return content.startswith(SESSION_MEMORY_MARKER)
