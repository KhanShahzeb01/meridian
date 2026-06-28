"""Ingest node — records turn snapshot without altering rallies runtime."""

from __future__ import annotations

from typing import Any

from ..langgraph_state import ShadowGraphState


def ingest_input_node(state: ShadowGraphState) -> dict[str, Any]:
    """Mark ingest complete; rallies payload is prepared before invoke."""
    rallies = state.get("rallies")
    if not isinstance(rallies, dict):
        rallies = {}
    return {"rallies": rallies, "last_node": "ingest_input"}
