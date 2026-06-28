"""Shared planner step helpers (legacy + graph paths)."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

_SYNTHESIS_KEYWORDS = [
    "compare",
    "versus",
    " vs ",
    "overall",
    "conclusion",
    "wrap up",
    "final analysis",
    "synthesize",
    "verdict",
]


def is_synthesis_step(item: dict[str, Any]) -> bool:
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    return any(keyword in text for keyword in _SYNTHESIS_KEYWORDS)


def cap_plan(plan: list[dict[str, Any]], max_steps: int) -> list[dict[str, Any]]:
    if len(plan) <= max_steps:
        return plan
    return plan[:max_steps]


def partition_plan_indices(plan: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    gather_idx = [i for i, item in enumerate(plan) if not is_synthesis_step(item)]
    synth_idx = [i for i, item in enumerate(plan) if is_synthesis_step(item)]
    return gather_idx, synth_idx


def run_gather_steps_parallel(
    agent: Any,
    prompt: str,
    plan: list[dict[str, Any]],
    gather_idx: list[int],
) -> tuple[list[Any], list[tuple[int, str]]]:
    """Run non-synthesis plan steps in parallel."""
    n = len(plan)
    action_results: list[Any] = [None] * n
    action_errors: list[tuple[int, str]] = []
    if not gather_idx:
        return action_results, action_errors

    with ThreadPoolExecutor(max_workers=max(1, len(gather_idx))) as executor:
        futures = {
            executor.submit(
                agent.action,
                prompt,
                plan[i]["title"],
                plan[i]["description"],
            ): i
            for i in gather_idx
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                action_results[index] = future.result()
            except Exception as exc:
                action_results[index] = str(exc)
                action_errors.append((index, str(exc)))
    return action_results, action_errors


def first_action_error(
    plan: list[dict[str, Any]],
    gather_idx: list[int],
    action_results: list[Any],
) -> tuple[dict[str, Any], str] | None:
    for index in gather_idx:
        result = action_results[index]
        if result and "[red]⚠" in str(result):
            return plan[index], str(result)
    return None


def run_synthesis_steps_sequential(
    agent: Any,
    prompt: str,
    plan: list[dict[str, Any]],
    synth_idx: list[int],
    workspace: list[dict[str, Any]],
    action_results: list[Any],
) -> tuple[list[Any], dict[str, Any] | None, str | None]:
    """Run synthesis steps sequentially; returns (results, failed_item, error)."""
    for index in synth_idx:
        item = plan[index]
        result = agent.action(
            prompt,
            item["title"],
            item["description"],
            workspace,
        )
        if "[red]⚠" in str(result):
            return action_results, item, str(result)
        action_results[index] = result
    return action_results, None, None


def summarize_plan_steps(
    agent: Any,
    plan: list[dict[str, Any]],
    workspace: list[dict[str, Any]],
    action_results: list[Any],
) -> tuple[list[dict[str, Any]], dict[int, str]]:
    """Append step data to workspace and summarize each step in parallel."""
    step_snapshots: list[list[dict[str, Any]]] = []
    for index, item in enumerate(plan):
        result = action_results[index]
        workspace.append(
            {"role": "user", "content": f"{item['title']} - {item['description']}"}
        )
        workspace.append({"role": "user", "content": str(result), "type": "data"})
        step_snapshots.append(list(workspace))

    summaries: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, len(plan))) as executor:
        future_map = {
            executor.submit(agent.summarize, snapshot): index
            for index, snapshot in enumerate(step_snapshots)
        }
        for future in as_completed(future_map):
            index = future_map[future]
            summaries[index] = future.result()

    for index, summary in summaries.items():
        workspace.append({"role": "user", "content": str(summary)})
    return workspace, summaries


def execute_plan_steps(
    agent: Any,
    prompt: str,
    plan: list[dict[str, Any]],
    workspace: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    dict[int, str],
    dict[str, str],
    dict[str, Any] | None,
    str | None,
]:
    """
    Execute one planner round: gather, synthesize, summarize.

    Returns (workspace, summaries, step_results, failed_item, error_message).
    """
    gather_idx, synth_idx = partition_plan_indices(plan)
    action_results, _errors = run_gather_steps_parallel(agent, prompt, plan, gather_idx)

    failure = first_action_error(plan, gather_idx, action_results)
    if failure:
        failed_item, message = failure
        return workspace, {}, {}, failed_item, message

    action_results, failed_item, failed_message = run_synthesis_steps_sequential(
        agent,
        prompt,
        plan,
        synth_idx,
        workspace,
        action_results,
    )
    if failed_item is not None and failed_message is not None:
        return workspace, {}, {}, failed_item, failed_message

    workspace, summaries = summarize_plan_steps(agent, plan, workspace, action_results)
    step_results = {
        str(index): str(action_results[index]) for index in range(len(plan))
    }
    return workspace, summaries, step_results, None, None


def sleep_poll_interval() -> None:
    """Small delay for live planning UI refresh loops."""
    time.sleep(0.5)
