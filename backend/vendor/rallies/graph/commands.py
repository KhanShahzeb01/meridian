"""Slash command handlers for graph debug tooling."""

from __future__ import annotations

from typing import Any


def handle_graph_status_command(console, manager: Any | None = None) -> bool:
    """Show LangGraph checkpoint debug info for the current session."""
    from .status import build_graph_status_lines

    for line in build_graph_status_lines(manager):
        console.print(line)
    return True
