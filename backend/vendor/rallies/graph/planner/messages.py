"""Planner LLM message preparation with optional memory digest."""

from __future__ import annotations

from typing import Any

from ..context import build_llm_context
from ..memory.marker import SESSION_MEMORY_MARKER
from ..state import RalliesState


def workspace_has_memory_digest(workspace: list[dict[str, Any]]) -> bool:
    for message in workspace:
        if not isinstance(message, dict):
            continue
        content = str(message.get("content") or "")
        if SESSION_MEMORY_MARKER in content:
            return True
    return False


def prepend_memory_digest_to_workspace(
    workspace: list[dict[str, Any]],
    rallies_state: RalliesState,
) -> list[dict[str, Any]]:
    """Inject structured memory digest once at the start of the turn workspace."""
    if workspace_has_memory_digest(workspace):
        return workspace
    messages = build_llm_context(rallies_state, include_memory_digest=True)
    for message in messages:
        if isinstance(message, dict) and SESSION_MEMORY_MARKER in str(
            message.get("content") or ""
        ):
            return [dict(message), *workspace]
    return workspace


def build_planner_input_messages(
    workspace: list[dict[str, Any]],
    rallies_state: RalliesState,
    *,
    include_memory_digest: bool,
) -> list[dict[str, Any]]:
    if include_memory_digest:
        return prepend_memory_digest_to_workspace(workspace, rallies_state)
    return list(workspace)
