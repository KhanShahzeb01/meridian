"""Build research graph context slices from manager + conversation."""

from __future__ import annotations

from typing import Any

from ..bridge import state_from_manager, state_from_turn
from ..defaults import empty_entities_state, empty_input_state, empty_memory_state
from .context import ResearchGraphContext


def rallies_slice_from_manager(
    manager: Any | None,
    query: str,
    conversation: list[dict],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    """Return (entities, memory, input_state) dicts."""
    if manager is not None:
        prompt = f"/research {query}".strip()
        state = state_from_manager(manager, prompt, conversation)
        return (
            dict(state["entities"]),
            dict(state["memory"]),
            dict(state["input"]),
        )

    state = state_from_turn(
        history_session=None,
        prompt=query,
        conversation=conversation,
        tier="free",
        thread_max_tokens=None,
    )
    return (
        dict(state["entities"]),
        dict(state["memory"]),
        dict(state["input"]),
    )


def build_research_graph_context(
    loop: Any,
    query: str,
    *,
    manager: Any | None = None,
    conversation: list[dict] | None = None,
) -> ResearchGraphContext:
    """Hydrate graph context memory from REPL session when available."""
    convo = list(conversation or [])
    entities, memory, input_state = rallies_slice_from_manager(manager, query, convo)

    if manager is not None and not memory.get("prefetched_market_block"):
        research = getattr(manager, "research_session", None)
        prefetch = getattr(research, "prefetched_market_block", None) if research else None
        if prefetch:
            memory["prefetched_market_block"] = str(prefetch)

    return ResearchGraphContext(
        loop=loop,
        memory=memory or empty_memory_state(),
        entities=entities or empty_entities_state(),
        input_state=input_state or empty_input_state(raw_prompt=query, effective_prompt=query),
    )
