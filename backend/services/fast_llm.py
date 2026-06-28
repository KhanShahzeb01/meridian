"""Meridian fast LLM — always use the free fast model with tight token limits."""

from __future__ import annotations

from typing import Any

FAST_MODEL = "openai/gpt-oss-120b:free"


def fast_prompt(
    llm: Any,
    messages: list[dict[str, str]],
    *,
    task_type: str = "summary",
    use_cache: bool = True,
) -> str:
    return str(
        llm.prompt(
            messages,
            task_type=task_type,
            force_model=FAST_MODEL,
            no_cache=not use_cache,
        )
    ).strip()
