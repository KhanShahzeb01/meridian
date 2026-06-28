"""Run up to N subagents in parallel (Wave 4 rank 17)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .runner import run_subagent
from .types import MAX_SUBAGENTS_PER_ROUND


def run_subagents_parallel(
    llm: Any,
    registry: Any,
    calls: list[dict],
    *,
    progress: Any | None = None,
    max_workers: int = MAX_SUBAGENTS_PER_ROUND,
) -> list[str]:
    """Each call dict: description, task, subagent_type?, context?."""
    capped = calls[:MAX_SUBAGENTS_PER_ROUND]
    if not capped:
        return []

    results: list[str | None] = [None] * len(capped)

    def _run_one(index: int, spec: dict) -> tuple[int, str]:
        desc = str(spec.get("description") or "subagent")[:80]
        if progress:
            progress.subagent_start(desc)
        answer = run_subagent(
            llm,
            registry,
            task=str(spec.get("task") or ""),
            context=spec.get("context"),
            subagent_type=spec.get("subagent_type"),
            progress=progress,
        )
        if progress:
            progress.subagent_done(desc)
        return index, answer

    workers = min(max_workers, len(capped))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_one, i, spec) for i, spec in enumerate(capped)]
        for future in as_completed(futures):
            index, answer = future.result()
            results[index] = answer

    return [r or "" for r in results]
