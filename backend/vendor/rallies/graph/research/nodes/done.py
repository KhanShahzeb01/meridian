"""Research terminal node."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from ..state import ResearchGraphState


def research_done_node(state: ResearchGraphState, config: RunnableConfig) -> dict[str, Any]:
    """Mark graph completion (answer already in state)."""
    _ = config
    return {"last_node": "research_done"}
