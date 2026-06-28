"""Dispatch /research to graph or legacy loop path."""

from __future__ import annotations

from typing import Any

from ..flags import graph_research_enabled, langgraph_available


def _session_id_from_manager(manager: Any | None) -> str | None:
    if manager is None:
        return None
    history = getattr(manager, "history_session", None)
    if not isinstance(history, dict):
        return None
    session_id = str(history.get("id") or "").strip()
    return session_id or None


def run_research_for_command(
    loop: Any,
    query: str,
    *,
    manager: Any | None = None,
    console: Any | None = None,
    conversation: list[dict] | None = None,
) -> str:
    """
    Run /research query.

    Uses LangGraph when RALLIES_GRAPH_RESEARCH=1 and langgraph is installed;
    otherwise delegates to ResearchLoop.run (unchanged default).
    """
    if not graph_research_enabled() or not langgraph_available():
        return loop.run(query)

    try:
        from .runner import run_research_graph

        return run_research_graph(
            loop,
            query,
            session_id=_session_id_from_manager(manager),
            manager=manager,
            conversation=conversation,
        )
    except Exception as exc:
        _log_graph_fallback(console, exc)
        return loop.run(query)


def _log_graph_fallback(console: Any | None, exc: Exception) -> None:
    message = f"research graph fallback to loop: {exc}"
    if console is not None:
        console.print(f"[dim]Graph research: {message}[/dim]")
        return
    try:
        from rallies import console as rallies_console

        rallies_console.print(f"[dim]Graph research: {message}[/dim]")
    except Exception:
        pass
