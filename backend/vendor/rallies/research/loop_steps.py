"""Shared research iteration steps (used by ResearchLoop and LangGraph path)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .loop import build_research_system_prompt
from .microcompact import microcompact_messages
from .tools import format_research_answer, parse_research_steps

if TYPE_CHECKING:
    from .loop import ResearchLoop


@dataclass
class DecideOutcome:
    raw: str
    all_tool_calls: list[dict]
    done_answer: str | None
    parse_error: str | None = None
    thinking: str | None = None


def build_initial_messages(query: str) -> list[dict]:
    return [
        {"role": "system", "content": build_research_system_prompt(query)},
        {"role": "user", "content": query},
    ]


def apply_microcompact(
    messages: list[dict],
    *,
    session: Any | None,
    progress: Any | None,
) -> list[dict]:
    mc = microcompact_messages(messages)
    if not mc.trigger:
        return messages
    if progress is not None:
        progress.microcompact(mc.cleared, mc.estimated_tokens_saved)
    if session is not None:
        session.scratchpad.add_thinking(
            f"Microcompact ({mc.trigger}): cleared {mc.cleared}"
        )
    return mc.messages


def run_llm_decide(
    loop: ResearchLoop,
    messages: list[dict],
    *,
    iteration: int,
) -> DecideOutcome:
    raw = loop.llm.prompt(messages, task_type="research", no_cache=True)
    if loop.session:
        loop.session.record_llm_tool(
            "research_llm",
            {"iteration": iteration},
            str(raw)[:12000],
        )
    try:
        steps = parse_research_steps(str(raw))
    except (ValueError, json.JSONDecodeError) as exc:
        return DecideOutcome(
            raw=str(raw),
            all_tool_calls=[],
            done_answer=None,
            parse_error=str(exc),
        )

    all_tool_calls: list[dict] = []
    done_answer: str | None = None
    captured_thinking: str | None = None
    for step in steps:
        thinking = step.get("thinking") or step.get("plan")
        if thinking:
            if captured_thinking is None and len(steps) == 1:
                captured_thinking = str(thinking)
            if loop.progress is not None:
                loop.progress.thinking(str(thinking))
            if loop.session:
                loop.session.scratchpad.add_thinking(str(thinking))
        calls = step.get("tool_calls") or []
        if isinstance(calls, list):
            all_tool_calls.extend(c for c in calls if isinstance(c, dict))
        action = str(step.get("action", "")).lower()
        if action == "done" or step.get("answer"):
            ans = step.get("answer")
            if ans and str(ans).strip():
                done_answer = str(ans).strip()

    return DecideOutcome(
        raw=str(raw),
        all_tool_calls=all_tool_calls,
        done_answer=done_answer,
        thinking=captured_thinking,
    )


def build_tool_calls_payload(
    tool_calls: list[dict],
    *,
    thinking: str | None = None,
) -> dict:
    payload: dict[str, Any] = {
        "action": "tool_calls",
        "tool_calls": tool_calls[:5],
    }
    if thinking:
        payload["thinking"] = thinking
    return payload


def append_tool_nudge(messages: list[dict]) -> None:
    messages.append(
        {
            "role": "user",
            "content": (
                "Tool results are above. Respond with a single JSON object "
                "action=done and a markdown answer using ONLY those tool results. "
                "Do not invent numbers."
            ),
        }
    )


def append_must_use_tools_nudge(messages: list[dict]) -> None:
    messages.append(
        {
            "role": "user",
            "content": (
                "You must call tools (e.g. research_fetch) before answering. "
                "Respond with one JSON object: action=tool_calls."
            ),
        }
    )


def append_format_nudge(messages: list[dict]) -> None:
    messages.append(
        {
            "role": "user",
            "content": (
                "Respond with one JSON object only: "
                "either action=tool_calls with tools, or action=done with markdown answer."
            ),
        }
    )


def finalize_done_answer(loop: ResearchLoop, answer: str, *, iteration: int) -> str:
    formatted = format_research_answer(answer)
    if loop.progress is not None:
        loop.progress.done(loop.executor.tool_call_count, iteration)
    if loop.session:
        loop.session.record_llm_tool(
            "research_answer",
            {"iterations": iteration},
            formatted[:12000],
        )
    return formatted


def parse_error_fallback(outcome: DecideOutcome) -> str:
    try:
        fallback = format_research_answer(outcome.raw)
    except (ValueError, json.JSONDecodeError):
        fallback = ""
    return fallback or f"Research parse error: {outcome.parse_error}"


def iteration_limit_answer(loop: ResearchLoop) -> str:
    if loop.progress is not None:
        loop.progress.done(loop.executor.tool_call_count, loop.max_iterations)
    return (
        "Research reached the iteration limit. "
        "Try a narrower question or check /research-log for tool output."
    )


def run_research_iterations(loop: ResearchLoop, query: str) -> str:
    """Core research tool loop (shared by ResearchLoop.run and graph runner)."""
    messages = build_initial_messages(query)
    if loop.session:
        loop.session.scratchpad.add_thinking(f"Research loop: {query[:200]}")

    for iteration in range(1, loop.max_iterations + 1):
        if loop.progress is not None:
            loop.progress.iteration(iteration, loop.max_iterations)

        messages = apply_microcompact(
            messages,
            session=loop.session,
            progress=loop.progress,
        )
        messages = loop._maybe_full_compact(messages, query)

        outcome = run_llm_decide(loop, messages, iteration=iteration)
        if outcome.parse_error:
            return parse_error_fallback(outcome)

        if outcome.all_tool_calls:
            payload = build_tool_calls_payload(
                outcome.all_tool_calls,
                thinking=outcome.thinking,
            )
            loop._execute_tool_calls(
                messages,
                outcome.all_tool_calls,
                assistant_payload=payload,
            )
            if outcome.done_answer:
                append_tool_nudge(messages)
            continue

        if outcome.done_answer:
            if loop.executor.tool_call_count == 0:
                append_must_use_tools_nudge(messages)
                continue
            return finalize_done_answer(loop, outcome.done_answer, iteration=iteration)

        if outcome.thinking and loop.session:
            loop.session.scratchpad.add_thinking(
                f"Non-JSON research response (retrying): {outcome.raw[:400]}"
            )
        append_format_nudge(messages)

    return iteration_limit_answer(loop)
