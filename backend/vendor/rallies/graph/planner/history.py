"""History JSONL helpers for planner orchestration."""

from __future__ import annotations

from typing import Any

from ...helpers import append_history_event, log_turn_aborted


def record_plan_generated(
    history_session: dict[str, Any],
    *,
    plan: list[dict[str, Any]],
    round_num: int,
    max_rounds: int,
) -> None:
    append_history_event(
        history_session,
        "plan_generated",
        {
            "plan": plan,
            "round": round_num,
            "max_rounds": max_rounds,
        },
    )


def record_plan_step_started(
    history_session: dict[str, Any],
    *,
    title: str,
    description: str,
) -> None:
    append_history_event(
        history_session,
        "plan_step_started",
        {"title": title, "description": description},
    )


def record_plan_step_completed(
    history_session: dict[str, Any],
    *,
    title: str,
    description: str,
    result: str,
    summary: str,
) -> None:
    append_history_event(
        history_session,
        "plan_step_completed",
        {
            "title": title,
            "description": description,
            "result": str(result),
            "summary": str(summary),
        },
    )


def record_plan_step_error(
    history_session: dict[str, Any],
    *,
    title: str,
    error: str,
) -> None:
    append_history_event(
        history_session,
        "plan_step_error",
        {"title": title, "error": error},
    )


def record_plan_step_failed_abort(
    history_session: dict[str, Any],
    *,
    error: str,
    step_title: str | None,
) -> None:
    log_turn_aborted(
        history_session,
        "plan_step_failed",
        error[:2000],
        step_title=step_title,
    )


def print_plan_failure_footer(console: Any) -> None:
    console.print(
        f"[dim white]Contact us at [/dim white]"
        f"[link=mailto:support@rallies.ai][white]support@rallies.ai[/white][/link] "
        f"[dim white]in case of any issues[/dim white]",
        justify="right",
    )
