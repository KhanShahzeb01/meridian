"""Research tools node — executes pending tool calls."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from rallies.research.loop_steps import append_tool_nudge, build_tool_calls_payload

from ..config import get_research_context
from ..state import ResearchGraphState


def research_tools_node(
    state: ResearchGraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    ctx = get_research_context(config)
    loop = ctx.loop
    messages = list(state.get("messages") or [])
    tool_calls = list(state.get("pending_tool_calls") or [])

    if not tool_calls:
        return {"last_node": "research_tools", "status": "running"}

    payload = build_tool_calls_payload(tool_calls)
    loop._execute_tool_calls(messages, tool_calls, assistant_payload=payload)

    if state.get("pending_done_answer"):
        append_tool_nudge(messages)

    return {
        "messages": messages,
        "pending_tool_calls": [],
        "pending_done_answer": None,
        "status": "running",
        "last_node": "research_tools",
    }
