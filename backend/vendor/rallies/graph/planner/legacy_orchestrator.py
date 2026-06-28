"""Default planner orchestration with Rich live planning UI."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner

from ... import console
from ...thread_memory import messages_for_planner
from .history import (
    print_plan_failure_footer,
    record_plan_generated,
    record_plan_step_completed,
    record_plan_step_error,
    record_plan_step_failed_abort,
    record_plan_step_started,
)
from .steps import cap_plan, partition_plan_indices, sleep_poll_interval


def run_planned_prompt_legacy(
    manager: Any,
    prompt: str,
    workspace: list,
    thread: list,
) -> str:
    """Existing Manager planner loop (unchanged behavior when graph flag is off)."""
    console.print()
    plan_spinner = Spinner("dots", text="[bright_magenta]Planning...[/bright_magenta]")
    with Live(plan_spinner, console=console, refresh_per_second=10):
        pass

    planning_content: list[str] = []
    with Live(console=console, refresh_per_second=10) as planning_live:
        planner_round = 0
        while planner_round < manager.max_planner_rounds:
            planner_round += 1
            resolved = getattr(manager, "_resolved_turn", None)
            prior_cmd = resolved.prior_command if resolved else None
            plan = manager.agent.run(
                messages_for_planner(
                    workspace,
                    prompt,
                    prior_command=prior_cmd,
                ),
                max_steps=manager.max_steps_per_round,
            )
            plan = cap_plan(plan, manager.max_steps_per_round)
            record_plan_generated(
                manager.history_session,
                plan=plan,
                round_num=planner_round,
                max_rounds=manager.max_planner_rounds,
            )
            if len(plan) == 0:
                break

            workspace.append({"role": "assistant", "content": str(plan)})
            error = _execute_plan_with_ui(
                manager,
                prompt,
                plan,
                workspace,
                planning_content,
                planning_live,
            )
            if error is not None:
                return error

    return manager._stream_final_answer(prompt, workspace, thread)


def _execute_plan_with_ui(
    manager: Any,
    prompt: str,
    plan: list[dict[str, Any]],
    workspace: list,
    planning_content: list[str],
    planning_live: Live,
) -> str | None:
    step_start = len(planning_content)
    _append_plan_queued_rows(plan, planning_content)
    planning_live.update(
        Panel("\n".join(planning_content), title="Planning", style="magenta")
    )

    gather_idx, synth_idx = partition_plan_indices(plan)
    action_results = _run_gather_with_ui(
        manager,
        prompt,
        plan,
        gather_idx,
        synth_idx,
        planning_content,
        planning_live,
        step_start,
    )
    if action_results is None:
        return ""

    action_results = _run_synthesis_with_ui(
        manager,
        prompt,
        plan,
        synth_idx,
        workspace,
        action_results,
        planning_content,
        planning_live,
        step_start,
    )
    if action_results is None:
        return ""

    _summarize_with_ui(
        manager,
        prompt,
        plan,
        workspace,
        action_results,
        planning_content,
        planning_live,
        step_start,
    )
    return None


def _append_plan_queued_rows(plan: list[dict[str, Any]], planning_content: list[str]) -> None:
    for item in plan:
        planning_content.append(
            f"[bright_green]●[/bright_green] [white]{item['description']}[/white]"
        )
        planning_content.append("[yellow]  Queued...[/yellow]")
        planning_content.append("")


def _run_gather_with_ui(
    manager: Any,
    prompt: str,
    plan: list[dict[str, Any]],
    gather_idx: list[int],
    synth_idx: list[int],
    planning_content: list[str],
    planning_live: Live,
    step_start: int,
) -> list[Any] | None:
    n = len(plan)
    action_results: list[Any] = [None] * n
    action_errors: list[tuple[int, str]] = []

    with ThreadPoolExecutor(max_workers=max(1, len(gather_idx))) as executor:
        futures = {
            executor.submit(
                manager.agent.action,
                prompt,
                plan[i]["title"],
                plan[i]["description"],
            ): i
            for i in gather_idx
        }
        remaining = dict(futures)
        action_start = time.time()
        while remaining:
            elapsed = int(time.time() - action_start)
            for index in gather_idx:
                if action_results[index] is not None:
                    continue
                row = step_start + 3 * index + 1
                planning_content[row] = f"[yellow]  Retrieving... ({elapsed}s)[/yellow]"
            for index in synth_idx:
                row = step_start + 3 * index + 1
                planning_content[row] = "[dim]  Waiting...[/dim]"
            planning_live.update(
                Panel("\n".join(planning_content), title="Planning", style="magenta")
            )
            done_this_round = [(future, index) for future, index in remaining.items() if future.done()]
            for future, index in done_this_round:
                try:
                    action_results[index] = future.result()
                except Exception as exc:
                    action_results[index] = str(exc)
                    action_errors.append((index, str(exc)))
                row = step_start + 3 * index + 1
                if action_errors and action_errors[-1][0] == index:
                    planning_content[row] = "[red]  Failed[/red]"
                else:
                    planning_content[row] = "[green]  Done[/green]"
                del remaining[future]
            if not remaining:
                break
            sleep_poll_interval()

    for index in gather_idx:
        result = action_results[index]
        if result and "[red]⚠" in str(result):
            item = plan[index]
            record_plan_step_error(
                manager.history_session,
                title=str(item.get("title") or ""),
                error=str(result),
            )
            record_plan_step_failed_abort(
                manager.history_session,
                error=str(result),
                step_title=item.get("title"),
            )
            planning_live.stop()
            console.print(result)
            console.print()
            print_plan_failure_footer(console)
            return None
    return action_results


def _run_synthesis_with_ui(
    manager: Any,
    prompt: str,
    plan: list[dict[str, Any]],
    synth_idx: list[int],
    workspace: list,
    action_results: list[Any],
    planning_content: list[str],
    planning_live: Live,
    step_start: int,
) -> list[Any] | None:
    for index in synth_idx:
        item = plan[index]
        row = step_start + 3 * index + 1
        planning_content[row] = "[yellow]  Analyzing...[/yellow]"
        planning_live.update(
            Panel("\n".join(planning_content), title="Planning", style="magenta")
        )
        result = manager.agent.action(
            prompt,
            item["title"],
            item["description"],
            workspace,
        )
        if "[red]⚠" in str(result):
            record_plan_step_error(
                manager.history_session,
                title=str(item.get("title") or ""),
                error=str(result),
            )
            record_plan_step_failed_abort(
                manager.history_session,
                error=str(result),
                step_title=item.get("title"),
            )
            planning_live.stop()
            console.print(result)
            console.print()
            return None
        action_results[index] = result
    return action_results


def _summarize_with_ui(
    manager: Any,
    prompt: str,
    plan: list[dict[str, Any]],
    workspace: list,
    action_results: list[Any],
    planning_content: list[str],
    planning_live: Live,
    step_start: int,
) -> None:
    del prompt
    step_snapshots: list[list] = []
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
            executor.submit(manager.agent.summarize, snapshot): index
            for index, snapshot in enumerate(step_snapshots)
        }
        for future in as_completed(future_map):
            index = future_map[future]
            summaries[index] = future.result()

    for index, item in enumerate(plan):
        result = action_results[index]
        summary = summaries.get(index, "")
        record_plan_step_started(
            manager.history_session,
            title=str(item.get("title") or ""),
            description=str(item.get("description") or ""),
        )
        record_plan_step_completed(
            manager.history_session,
            title=str(item.get("title") or ""),
            description=str(item.get("description") or ""),
            result=str(result),
            summary=str(summary),
        )
        workspace.append({"role": "user", "content": str(summary)})
        row = step_start + 3 * index + 1
        planning_content[row] = (
            f"[white]└─[/white] [bright_black]{summary}[/bright_black]"
        )
        planning_live.update(
            Panel("\n".join(planning_content), title="Planning", style="magenta")
        )
