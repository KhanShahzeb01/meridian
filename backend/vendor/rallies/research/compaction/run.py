"""Run full LLM compaction on accumulated tool results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .prompt import build_compact_summary_message, build_compaction_prompt
from ..prompt_overlay import research_system_prefix


@dataclass(frozen=True)
class CompactionResult:
    summary: str
    raw_summary: str


def compact_tool_results(
    llm: Any,
    query: str,
    tool_results: str,
    *,
    system_prefix: str | None = None,
) -> CompactionResult:
    if not (tool_results or "").strip():
        raise ValueError("No tool results to compact")

    prefix = system_prefix if system_prefix is not None else research_system_prefix()
    prompt_text = build_compaction_prompt(query, tool_results)
    messages = [
        {"role": "system", "content": (prefix or "You summarize financial research tool output.")},
        {"role": "user", "content": prompt_text},
    ]
    raw = llm.prompt(messages, task_type="compact", no_cache=True)
    raw_summary = str(raw or "").strip()
    if not raw_summary:
        raise ValueError("Compaction returned empty response")
    summary = build_compact_summary_message(raw_summary)
    return CompactionResult(summary=summary, raw_summary=raw_summary)
