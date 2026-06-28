"""Isolated mini research loop for spawn_subagent (Wave 4 rank 17)."""

from __future__ import annotations

import json
from typing import Any

from .types import SubagentTypeConfig, resolve_subagent_type
from ..tools import ResearchToolExecutor, format_research_answer, parse_research_steps

_SUBAGENT_SYSTEM = """You are a focused financial subagent for Rallies CLI.

Complete ONLY the delegated task below using tools. You cannot spawn further subagents.
Respond with one JSON object per turn:

{{"action": "tool_calls", "thinking": "...", "tool_calls": [{{"name": "...", "arguments": {{}}}}]}}
or
{{"action": "done", "answer": "<markdown>"}}

Use only the tools listed. Cite numbers from tool results only.

## Tools
{tools}
"""


def build_subagent_system_prompt(config: SubagentTypeConfig) -> str:
    from ..tools import RESEARCH_TOOLS

    allowed = config.allowed_tools
    blocks = []
    for tool in RESEARCH_TOOLS:
        if tool.name not in allowed:
            continue
        blocks.append(
            f"### {tool.name}\n{tool.description}\n"
            f"Parameters: {json.dumps(tool.parameters, separators=(',', ':'))}"
        )
    return _SUBAGENT_SYSTEM.format(tools="\n\n".join(blocks))


def run_subagent(
    llm: Any,
    registry: Any,
    *,
    task: str,
    context: str | None = None,
    subagent_type: str | None = None,
    progress: Any | None = None,
) -> str:
    config = resolve_subagent_type(subagent_type)
    user_parts = [f"## Task\n{task.strip()}"]
    if context and context.strip():
        user_parts.append(f"## Context\n{context.strip()}")
    user_content = "\n\n".join(user_parts)

    messages: list[dict] = [
        {"role": "system", "content": build_subagent_system_prompt(config)},
        {"role": "user", "content": user_content},
    ]

    executor = ResearchToolExecutor(
        registry,
        session=None,
        progress=progress,
        llm=None,
        allow_subagents=False,
        allowed_tools=config.allowed_tools,
    )

    for iteration in range(1, config.max_iterations + 1):
        if progress:
            progress.subagent_round(config.name, iteration, config.max_iterations)

        raw = llm.prompt(messages, task_type="research", no_cache=True)
        try:
            steps = parse_research_steps(str(raw))
        except (ValueError, json.JSONDecodeError) as e:
            return f"Subagent parse error: {e}"

        tool_calls: list[dict] = []
        done_answer: str | None = None
        for step in steps:
            calls = step.get("tool_calls") or []
            if isinstance(calls, list):
                tool_calls.extend(c for c in calls if isinstance(c, dict))
            if str(step.get("action", "")).lower() == "done" or step.get("answer"):
                ans = step.get("answer")
                if ans and str(ans).strip():
                    done_answer = str(ans).strip()

        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {"action": "tool_calls", "tool_calls": tool_calls[:3]},
                        ensure_ascii=False,
                    ),
                }
            )
            for call in tool_calls[:3]:
                name = str(call.get("name", "")).strip()
                args = call.get("arguments") or call.get("args") or {}
                if not isinstance(args, dict):
                    args = {}
                result = executor.execute(name, args)
                messages.append({"role": "tool", "name": name, "content": result})
            if done_answer:
                continue
            continue

        if done_answer:
            if executor.tool_call_count == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": "Call a tool first, then respond with action=done.",
                    }
                )
                continue
            return format_research_answer(done_answer)

    return (
        f"Subagent ({config.name}) hit iteration limit. "
        f"Partial work: {executor.tool_call_count} tool call(s)."
    )
