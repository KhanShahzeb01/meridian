"""Feature flags for optional LangGraph integration."""

from __future__ import annotations

import os


def _env_truthy(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_falsy(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"0", "false", "no", "off"}


def graph_research_enabled() -> bool:
    """
    When enabled, /research uses LangGraph subgraph instead of inline loop.

    Env: RALLIES_GRAPH_RESEARCH=1
    """
    return _env_truthy("RALLIES_GRAPH_RESEARCH")


def graph_checkpoints_enabled() -> bool:
    """
    When enabled, shadow graph checkpoints run after each LLM turn.

    Env: RALLIES_GRAPH_CHECKPOINTS=1
    """
    return _env_truthy("RALLIES_GRAPH_CHECKPOINTS")


def graph_planner_enabled() -> bool:
    """
    When enabled, free-text prompts use LangGraph planner subgraph.

    Env: RALLIES_GRAPH_PLANNER=1
    """
    return _env_truthy("RALLIES_GRAPH_PLANNER")


def graph_memory_enabled() -> bool:
    """
    Structured session memory: digest in graph research + tool dual-write.

    Env: RALLIES_GRAPH_MEMORY=1
    Set RALLIES_GRAPH_MEMORY=0 to disable even when graph research is on.
    """
    if _env_falsy("RALLIES_GRAPH_MEMORY"):
        return False
    return _env_truthy("RALLIES_GRAPH_MEMORY") or graph_research_enabled()


def turn_pair_memory_enabled() -> bool:
    """
    Persist user query + final answer pairs to .rallies/memory/{session_id}.json.

    On by default. Set RALLIES_GRAPH_MEMORY=0 to disable.
    """
    if _env_falsy("RALLIES_GRAPH_MEMORY"):
        return False
    return True


def planner_memory_digest_enabled() -> bool:
    """
    Inject structured tool/plan digest into planner LLM calls.

    Disabled when turn-pair memory is active — prior turns are loaded as
    user/assistant pairs instead of planner/tool summaries.
    """
    if _env_falsy("RALLIES_GRAPH_MEMORY"):
        return False
    if turn_pair_memory_enabled():
        return False
    return graph_planner_enabled() or graph_memory_enabled()


def langgraph_available() -> bool:
    """Return True when optional langgraph dependencies are installed."""
    try:
        import langgraph  # noqa: F401
        import langgraph.checkpoint.sqlite  # noqa: F401

        return True
    except ImportError:
        return False
