"""Dispatch free-text planner flow to graph or legacy orchestrator."""

from __future__ import annotations

from typing import Any

from ..flags import graph_planner_enabled, langgraph_available
from .legacy_orchestrator import run_planned_prompt_legacy


def run_planned_prompt(
    manager: Any,
    prompt: str,
    workspace: list,
    thread: list,
) -> str:
    """
    Run Manager planner loop.

    Uses LangGraph when RALLIES_GRAPH_PLANNER=1 and langgraph is installed;
    otherwise delegates to legacy orchestrator (unchanged default).
    """
    if graph_planner_enabled() and langgraph_available():
        try:
            from .runner import run_planner_graph

            return run_planner_graph(manager, prompt, workspace, thread)
        except Exception as exc:
            _log_graph_fallback(exc)
    return run_planned_prompt_legacy(manager, prompt, workspace, thread)


def _log_graph_fallback(exc: Exception) -> None:
    try:
        from rallies import console as rallies_console

        rallies_console.print(f"[dim]Graph planner: fallback to legacy ({exc})[/dim]")
    except Exception:
        pass
