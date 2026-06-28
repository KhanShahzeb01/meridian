"""LangGraph /research subgraph (Phase 3)."""

from .dispatch import run_research_for_command

__all__ = ["run_research_for_command", "run_research_graph"]


def __getattr__(name: str):
    if name == "run_research_graph":
        from .runner import run_research_graph

        return run_research_graph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
