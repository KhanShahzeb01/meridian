"""Typed state buckets for LangGraph orchestration (Phase 0 — schema only)."""

from __future__ import annotations

from typing import Any, TypedDict


class SessionState(TypedDict):
    """Persistent session identity and limits."""

    id: str
    started_at: str
    file_path: str
    tier: str
    thread_max_tokens: int


class InputState(TypedDict):
    """Raw user line and planner-facing effective prompt."""

    raw_prompt: str
    effective_prompt: str


class EntitiesState(TypedDict):
    """Tickers and compound-command context extracted for this turn."""

    active_tickers: list[str]
    query_tickers: list[str]
    compound_sources: list[str]
    compound_tickers: list[str]


class ThreadState(TypedDict):
    """Cross-turn user/assistant messages (REPL thread)."""

    messages: list[dict[str, Any]]


class MemoryState(TypedDict):
    """Structured recall for LLM context and deduplicated market data."""

    market_snapshots: dict[str, str]
    tool_results: list[dict[str, Any]]
    plans: list[dict[str, Any]]
    prefetched_market_block: str | None


class ResearchState(TypedDict):
    """Per-turn research observability (mirrors ResearchSession fields)."""

    query: str | None
    scratchpad_path: str | None
    is_follow_up: bool
    prior_turn_count: int


class OutputState(TypedDict):
    """Turn output and routing metadata."""

    final_answer: str | None
    route: str | None


class ControlState(TypedDict):
    """Feature flags and graph routing (populated in later phases)."""

    graph_enabled: bool


class RalliesState(TypedDict):
    """Unified rallies session state — source of truth for future graph nodes."""

    session: SessionState
    input: InputState
    entities: EntitiesState
    thread: ThreadState
    memory: MemoryState
    research: ResearchState
    output: OutputState
    control: ControlState
