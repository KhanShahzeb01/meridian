"""Dexter-style research tool loop (Wave 3 rank 15)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Iterator

from .compaction import (
    FULL_COMPACT_TOKEN_THRESHOLD,
    FULL_COMPACT_TOOL_COUNT_THRESHOLD,
    MAX_CONSECUTIVE_COMPACTION_FAILURES,
    apply_compaction_to_messages,
    collect_tool_results_text,
    compact_tool_results,
    estimate_messages_tokens,
    should_run_full_compaction,
)
from .progress import ResearchProgress
from .prompt_overlay import research_system_prefix
from .skills.registry import build_skill_metadata_section, suggest_skills_for_query
from .subagent.parallel import run_subagents_parallel
from .tools import (
    ResearchToolExecutor,
    build_research_tools_prompt,
)
from .units import DOLLAR_UNIT_RULES

DEFAULT_MAX_ITERATIONS = 8

RESEARCH_SYSTEM_TEMPLATE = """You are a financial research agent for Rallies CLI.

Today's date: {today}

You MUST use tools to retrieve live data before answering market or financial questions.
Do NOT invent prices, margins, EPS, or filing text. Only cite numbers that appear in tool results.

Respond with **exactly one** JSON object per turn — never multiple JSON blobs in one message.
Do not combine `tool_calls` and `done` in the same response.

When you need data:
{{"action": "tool_calls", "thinking": "<brief plan>", "tool_calls": [{{"name": "<tool>", "arguments": {{...}}}}]}}

When you have enough verified data from tool results in this conversation:
{{"action": "done", "answer": "<markdown answer citing tool data and dates>"}}

Rules:
- Run tools first; only use `done` after tool results are in the conversation.
- For compare questions, call load_skill compare-equities then research_fetch_multi.
- For memo/thesis, call load_skill write-memo then gather_equity_bundle and write_memo_html.
- For DCF/fair value, call load_skill dcf-valuation then run_dcf_quant.
- For macro/FRED/rates/inflation, call load_skill fred-economic-data then macro_snapshot.
- For SEC/filings/10-K/MD&A, call load_skill edgartools then filing_section and gather_equity_bundle.
- For hedge fund leverage/systemic risk/repo, call load_skill hedgefundmonitor then hedgefund_snapshot.
- For A/B tests, p-values, sample size, call load_skill statistical-analyst (reasoning; no scripts).
- Narrow risk-only asks may use load_skill sec-risk-review then filing_section.
- Use filing_section for SEC narrative sections (risk factors, MD&A).
- Keep tool_calls to 1-3 per round.
- For independent deep dives on multiple tickers, use spawn_subagent (max 3 parallel).

{dollar_units}

{suggested_skills}

{overlay}

## Available skills
{skills}

## Tools
{tools}
"""


def build_research_system_prompt(query: str | None = None) -> str:
    suggested = ""
    if query:
        names = suggest_skills_for_query(query)
        if names:
            suggested = (
                "## Suggested skills for this query\n\n"
                "Call `load_skill` first for: "
                + ", ".join(f"`{n}`" for n in names)
                + ", then follow that skill's tool sequence.\n"
            )
    return RESEARCH_SYSTEM_TEMPLATE.format(
        today=date.today().isoformat(),
        dollar_units=DOLLAR_UNIT_RULES,
        suggested_skills=suggested.strip(),
        overlay=research_system_prefix().strip(),
        skills=build_skill_metadata_section(),
        tools=build_research_tools_prompt(),
    )


class ResearchLoop:
    """Additive /research mode — does not replace planner JSON flow."""

    def __init__(
        self,
        llm: Any,
        registry: Any,
        *,
        session: Any | None = None,
        progress: ResearchProgress | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.session = session
        self.progress = progress or ResearchProgress()
        self.max_iterations = max_iterations
        self._compaction_failures = 0
        self.executor = ResearchToolExecutor(
            registry,
            session=session,
            progress=self.progress,
            llm=llm,
            allow_subagents=True,
        )

    def _maybe_full_compact(self, messages: list[dict], query: str) -> list[dict]:
        if self._compaction_failures >= MAX_CONSECUTIVE_COMPACTION_FAILURES:
            return messages
        if not should_run_full_compaction(
            messages,
            token_threshold=FULL_COMPACT_TOKEN_THRESHOLD,
            tool_count_threshold=FULL_COMPACT_TOOL_COUNT_THRESHOLD,
        ):
            return messages

        tool_text = collect_tool_results_text(messages)
        pre_tokens = estimate_messages_tokens(messages)
        try:
            result = compact_tool_results(self.llm, query, tool_text)
        except Exception as e:
            self._compaction_failures += 1
            self.progress.compaction(pre_tokens, pre_tokens, success=False)
            if self.session:
                self.session.scratchpad.add_thinking(f"Compaction failed: {e}")
            return messages

        compacted = apply_compaction_to_messages(messages, result.summary)
        post_tokens = estimate_messages_tokens(compacted)
        self._compaction_failures = 0
        self.progress.compaction(pre_tokens, post_tokens, success=True)
        if self.session:
            self.session.scratchpad.add_thinking(
                f"Full compaction: ~{pre_tokens} → ~{post_tokens} tokens"
            )
            self.session.record_llm_tool(
                "research_compaction",
                {"query": query[:120]},
                result.raw_summary[:8000],
            )
        return compacted

    def _execute_tool_calls(
        self,
        messages: list[dict],
        tool_calls: list[dict],
        *,
        assistant_payload: dict,
    ) -> None:
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(assistant_payload, ensure_ascii=False),
            }
        )
        subagent_calls: list[dict] = []
        normal_calls: list[dict] = []
        for call in tool_calls[:5]:
            if not isinstance(call, dict):
                continue
            name = str(call.get("name", "")).strip()
            if name == "spawn_subagent" and self.executor.allow_subagents:
                subagent_calls.append(call)
            else:
                normal_calls.append(call)

        if subagent_calls:
            specs = []
            for call in subagent_calls:
                args = call.get("arguments") or call.get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                if not isinstance(args, dict):
                    args = {}
                specs.append(args)
            answers = run_subagents_parallel(
                self.llm,
                self.registry,
                specs,
                progress=self.progress,
            )
            for call, answer in zip(subagent_calls, answers):
                args = call.get("arguments") or call.get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                if not isinstance(args, dict):
                    args = {}
                desc = str(args.get("description") or "subagent")
                self.executor.tool_call_count += 1
                if self.session:
                    self.session.record_data_tool(
                        "spawn_subagent",
                        args,
                        answer[:8000],
                    )
                messages.append(
                    {
                        "role": "tool",
                        "name": "spawn_subagent",
                        "content": f"## Subagent: {desc}\n\n{answer}",
                    }
                )

        for call in normal_calls:
            name = str(call.get("name", "")).strip()
            arguments = call.get("arguments") or call.get("args") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": arguments}
            if not isinstance(arguments, dict):
                arguments = {}
            result = self.executor.execute(name, arguments)
            messages.append({"role": "tool", "name": name, "content": result})

    def run(self, query: str) -> str:
        from .loop_steps import run_research_iterations

        return run_research_iterations(self, query)

    def run_stream(self, query: str) -> Iterator[str]:
        """Non-streaming fallback — yields single final chunk."""
        yield self.run(query)
