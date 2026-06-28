"""Run independent read-only fetch tasks in parallel (Wave 2 rank 7)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar

T = TypeVar("T")


def run_parallel_tasks(
    tasks: dict[str, Callable[[], T]],
    *,
    max_workers: int | None = None,
) -> dict[str, T | Exception]:
    """
    Execute named callables concurrently. Exceptions are returned as values
    (not raised) so callers can format partial results.
    """
    if not tasks:
        return {}
    workers = max_workers or min(8, len(tasks))
    results: dict[str, T | Exception] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as exc:
                results[name] = exc
    return results
