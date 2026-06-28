"""Attach structured-memory dual-write to ResearchToolExecutor."""

from __future__ import annotations

from typing import Any

from ..flags import graph_memory_enabled
from .memory import record_tool_in_memory


def _on_tool_result(ctx: Any, tool_name: str, arguments: dict[str, Any], result: str) -> None:
    ctx.memory = record_tool_in_memory(
        dict(ctx.memory or {}),
        tool_name=tool_name,
        arguments=arguments,
        result=result,
    )


def attach_memory_callback_to_context(ctx: Any) -> None:
    """Wire executor callback when structured memory is enabled."""
    if not graph_memory_enabled():
        return
    loop = getattr(ctx, "loop", None)
    if loop is None:
        return
    executor = getattr(loop, "executor", None)
    if executor is None:
        return

    def callback(name: str, arguments: dict[str, Any], result: str) -> None:
        _on_tool_result(ctx, name, arguments, result)

    executor.on_tool_result = callback


def attach_memory_callback_for_loop(
    loop: Any,
    *,
    entities: dict[str, Any],
    memory: dict[str, Any],
) -> Any:
    """
    Legacy /research loop path: attach callback to a simple memory holder.

    Returns the holder (mutated in place on tool calls).
    """
    if not graph_memory_enabled():
        return None

    holder = SimpleMemoryHolder(entities=entities, memory=memory)

    def callback(name: str, arguments: dict[str, Any], result: str) -> None:
        holder.memory = record_tool_in_memory(
            dict(holder.memory),
            tool_name=name,
            arguments=arguments,
            result=result,
        )

    executor = getattr(loop, "executor", None)
    if executor is not None:
        executor.on_tool_result = callback
    return holder


class SimpleMemoryHolder:
    """Minimal mutable holder for legacy loop memory dual-write."""

    def __init__(self, *, entities: dict[str, Any], memory: dict[str, Any]) -> None:
        self.entities = entities
        self.memory = memory
