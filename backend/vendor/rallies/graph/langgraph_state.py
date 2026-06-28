"""LangGraph-compatible shadow state wrapper."""

from __future__ import annotations

from typing import Any, TypedDict


class ShadowGraphState(TypedDict):
    """Minimal graph state persisted by SqliteSaver (Phase 2)."""

    rallies: dict[str, Any]
    last_node: str
