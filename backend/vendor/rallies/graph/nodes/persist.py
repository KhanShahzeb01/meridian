"""Persist node — terminal marker before checkpoint write."""

from __future__ import annotations

from typing import Any

from ..langgraph_state import ShadowGraphState


def persist_turn_node(state: ShadowGraphState) -> dict[str, Any]:
    """Mark turn persisted; SqliteSaver writes after this node."""
    return {"last_node": "persist_turn"}
