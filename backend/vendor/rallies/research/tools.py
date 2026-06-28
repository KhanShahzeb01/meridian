"""Research-mode tool definitions and executor (Wave 3 ranks 10, 15)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# JSON only allows these single-char escapes after backslash.
_VALID_JSON_ESCAPE_CHARS = frozenset('"\\/bfnrtu')
_INVALID_JSON_ESCAPE_RE = re.compile(r"\\(.)")


def _repair_llm_json_text(text: str) -> str:
    """Fix invalid escape sequences LLMs emit inside JSON strings (e.g. \\$)."""

    def _fix(match: re.Match[str]) -> str:
        ch = match.group(1)
        if ch in _VALID_JSON_ESCAPE_CHARS:
            return match.group(0)
        return ch

    return _INVALID_JSON_ESCAPE_RE.sub(_fix, text)


def _loads_llm_json(text: str) -> Any:
    return json.loads(_repair_llm_json_text(text))

from .filing.section_fetch import fetch_filing_section, format_filing_section
from .meta.market_snapshots import hedgefund_snapshot, macro_snapshot
from .meta.research_fetch import research_fetch, research_fetch_multi
from .skills.actions import gather_equity_bundle, run_dcf_quant, write_memo_html
from .skills.registry import get_skill
from .tool_results import spill_if_large
from .web import fetch_url


@dataclass(frozen=True)
class ResearchToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


RESEARCH_TOOLS: list[ResearchToolSpec] = [
    ResearchToolSpec(
        name="macro_snapshot",
        description=(
            "FRED macro dashboard: Fed funds, CPI, unemployment, 10Y yield, GDP. "
            "Use with fred-economic-data skill. No ticker required."
        ),
        parameters={"type": "object", "properties": {}, "required": []},
    ),
    ResearchToolSpec(
        name="hedgefund_snapshot",
        description=(
            "OFR Hedge Fund Monitor: leverage, AUM, repo volumes. "
            "Use with hedgefundmonitor skill. No ticker required."
        ),
        parameters={"type": "object", "properties": {}, "required": []},
    ),
    ResearchToolSpec(
        name="research_fetch",
        description=(
            "Fetch market data for one ticker from rallies sources. "
            "Set intent to guide routing: quote, financials, margins, news, insider, "
            "filing, macro, hedge fund, vix."
        ),
        parameters={
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                "intent": {"type": "string", "description": "Natural language data intent"},
            },
            "required": ["ticker", "intent"],
        },
    ),
    ResearchToolSpec(
        name="research_fetch_multi",
        description="Fetch the same intent for multiple tickers (compare questions).",
        parameters={
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-5 ticker symbols",
                },
                "intent": {"type": "string", "description": "Natural language data intent"},
            },
            "required": ["tickers", "intent"],
        },
    ),
    ResearchToolSpec(
        name="filing_section",
        description=(
            "Read a SEC filing section via edgartools (not Financial Datasets). "
            "Examples: risk factors, MD&A, business description."
        ),
        parameters={
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "section": {"type": "string", "description": "NL section query"},
                "form": {"type": "string", "description": "Optional: 10-K or 10-Q"},
            },
            "required": ["ticker", "section"],
        },
    ),
    ResearchToolSpec(
        name="web_fetch",
        description="Fetch a public URL and return markdown text.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    ),
    ResearchToolSpec(
        name="load_skill",
        description=(
            "Load a SKILL.md workflow (dcf-valuation, write-memo, compare-equities, "
            "earnings-digest, sec-risk-review, fred-economic-data, edgartools, "
            "hedgefundmonitor, statistical-analyst). Call FIRST when the query matches."
        ),
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Skill name or folder"}},
            "required": ["name"],
        },
    ),
    ResearchToolSpec(
        name="run_dcf_quant",
        description="Run rallies DCF quant engine (same as /dcf). Returns fair value and assumptions.",
        parameters={
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "growth_rate": {"type": "number", "description": "Default 0.10"},
                "wacc": {"type": "number", "description": "Default 0.09"},
            },
            "required": ["ticker"],
        },
    ),
    ResearchToolSpec(
        name="gather_equity_bundle",
        description=(
            "One-shot pull: quote, financials, margins, news, insider, SEC filings, "
            "business + risk excerpts. Use before write-memo or earnings-digest."
        ),
        parameters={
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    ),
    ResearchToolSpec(
        name="write_memo_html",
        description="Save investment memo HTML to .rallies/memos/TICKER_DIRECTION_DATE.html",
        parameters={
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "direction": {"type": "string", "description": "LONG or SHORT"},
                "html_content": {"type": "string", "description": "Full rendered HTML document"},
            },
            "required": ["ticker", "direction", "html_content"],
        },
    ),
    ResearchToolSpec(
        name="spawn_subagent",
        description=(
            "Delegate a focused sub-task to an isolated subagent (max 3 parallel per round). "
            "Types: research (quotes, filings, web_fetch), analysis (financials, DCF, bundle)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Short 3–5 word label for UI",
                },
                "task": {"type": "string", "description": "Self-contained instruction"},
                "subagent_type": {
                    "type": "string",
                    "description": "research or analysis",
                },
                "context": {
                    "type": "string",
                    "description": "Optional background the subagent cannot see",
                },
            },
            "required": ["description", "task"],
        },
    ),
]

_TOOL_MAP = {t.name: t for t in RESEARCH_TOOLS}


def build_research_tools_prompt() -> str:
    blocks = []
    for tool in RESEARCH_TOOLS:
        blocks.append(
            f"### {tool.name}\n{tool.description}\n"
            f"Parameters JSON schema: {json.dumps(tool.parameters, separators=(',', ':'))}"
        )
    return "\n\n".join(blocks)


def _normalize_tickers(raw: Any) -> list[str]:
    if isinstance(raw, str):
        parts = [p.strip().upper() for p in raw.replace(",", " ").split() if p.strip()]
        return parts[:5]
    if isinstance(raw, list):
        return [str(t).upper().strip() for t in raw if str(t).strip()][:5]
    return []


class ResearchToolExecutor:
    """Execute research-loop tools with scratchpad + spill integration."""

    def __init__(
        self,
        registry: Any,
        session: Any | None = None,
        progress: Any | None = None,
        *,
        llm: Any | None = None,
        allow_subagents: bool = True,
        allowed_tools: frozenset[str] | None = None,
        on_tool_result: Callable[[str, dict[str, Any], str], None] | None = None,
    ) -> None:
        self.registry = registry
        self.session = session
        self.progress = progress
        self.llm = llm
        self.allow_subagents = allow_subagents
        self.allowed_tools = allowed_tools
        self.on_tool_result = on_tool_result
        self.tool_call_count = 0

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        if self.allowed_tools is not None and name not in self.allowed_tools:
            return f"Tool not allowed in this context: {name}"

        self.tool_call_count += 1
        if self.progress:
            self.progress.tool_start(name, arguments)

        if self.session:
            check = self.session.check_tool(name, json.dumps(arguments, sort_keys=True))
            if not check.allowed:
                return f"Tool limit reached for {name}: {check.warning or 'too many calls'}"

        try:
            result = self._dispatch(name, arguments or {})
        except Exception as e:
            result = f"Tool error ({name}): {e}"

        spilled = spill_if_large(result, label=name)
        result_text = spilled.text

        if self.session:
            self.session.record_data_tool(name, arguments or {}, result_text)
            if spilled.spilled:
                self.session.scratchpad.add_thinking(
                    f"Spilled {name} result ({spilled.original_chars} chars) to {spilled.path}"
                )

        if self.progress:
            self.progress.tool_done(name, len(result_text))
        self._notify_tool_result(name, arguments or {}, result_text)
        return result_text

    def _notify_tool_result(
        self,
        name: str,
        arguments: dict[str, Any],
        result_text: str,
    ) -> None:
        callback = self.on_tool_result
        if callback is None:
            return
        try:
            callback(name, arguments, result_text)
        except Exception:
            return

    def _dispatch(self, name: str, args: dict[str, Any]) -> str:
        if name == "macro_snapshot":
            return macro_snapshot(self.registry)

        if name == "hedgefund_snapshot":
            return hedgefund_snapshot(self.registry)

        if name == "research_fetch":
            ticker = str(args.get("ticker", "")).upper().strip()
            intent = str(args.get("intent", "quote"))
            return research_fetch(self.registry, ticker, intent)

        if name == "research_fetch_multi":
            tickers = _normalize_tickers(args.get("tickers"))
            intent = str(args.get("intent", "financials"))
            if len(tickers) < 2:
                return "research_fetch_multi requires at least 2 tickers"
            return research_fetch_multi(self.registry, tickers, intent)

        if name == "filing_section":
            ticker = str(args.get("ticker", "")).upper().strip()
            section = str(args.get("section", "risk factors"))
            form = args.get("form")
            result = fetch_filing_section(ticker, section, form=form)
            return format_filing_section(result)

        if name == "web_fetch":
            url = str(args.get("url", "")).strip()
            payload = fetch_url(url)
            title = payload.get("title") or url
            body = payload.get("markdown") or ""
            return f"# {title}\n\n{body}"

        if name == "load_skill":
            skill_name = str(args.get("name", "")).strip()
            skill = get_skill(skill_name)
            if not skill:
                return f"Skill not found: {skill_name}. Try /skill to list skills."
            return f"# Skill: {skill.name}\n\n{skill.instructions}"

        if name == "run_dcf_quant":
            ticker = str(args.get("ticker", "")).upper().strip()
            growth = float(args.get("growth_rate", 0.10))
            wacc = float(args.get("wacc", 0.09))
            return run_dcf_quant(ticker, growth_rate=growth, wacc=wacc)

        if name == "gather_equity_bundle":
            ticker = str(args.get("ticker", "")).upper().strip()
            return gather_equity_bundle(self.registry, ticker)

        if name == "write_memo_html":
            ticker = str(args.get("ticker", "")).upper().strip()
            direction = str(args.get("direction", "LONG"))
            html = str(args.get("html_content", ""))
            if len(html) < 200:
                return "write_memo_html: html_content too short (need full memo HTML)"
            meta = write_memo_html(ticker, direction, html)
            return (
                f"Memo saved: {meta['path']}\n"
                f"Open: file://{meta['path']}\n"
                f"({meta['ticker']} {meta['direction']})"
            )

        if name == "spawn_subagent":
            return (
                "spawn_subagent must be handled by the research loop "
                "(not the executor directly)."
            )

        return f"Unknown tool: {name}"


def extract_json_objects(text: str) -> list[dict[str, Any]]:
    """Extract one or more top-level JSON objects from model output (handles concatenated blobs)."""
    raw = (text or "").strip()
    if not raw:
        return []

    objects: list[dict[str, Any]] = []
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] != "{":
            i += 1
            continue
        depth = 0
        start = i
        in_string = False
        escape = False
        closed_at: int | None = None
        for j in range(i, n):
            ch = raw[j]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    closed_at = j
                    break
        if closed_at is None:
            break
        chunk = raw[start : closed_at + 1]
        try:
            data = _loads_llm_json(chunk)
            if isinstance(data, dict):
                objects.append(data)
        except json.JSONDecodeError:
            pass
        i = closed_at + 1
    return objects


def parse_research_response(raw: str) -> dict[str, Any]:
    """Parse a single research-step JSON object from model output."""
    objects = extract_json_objects(raw)
    if objects:
        return objects[0]

    text = (raw or "").strip()
    if not text:
        raise ValueError("Empty research response")

    candidates = [text]

    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE):
        candidates.append(m.group(1).strip())
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    last_err: Exception | None = None
    for cand in candidates:
        try:
            data = _loads_llm_json(cand)
        except json.JSONDecodeError as e:
            last_err = e
            continue
        if isinstance(data, dict):
            return data
    raise last_err or ValueError("Could not parse research JSON")


def parse_research_steps(raw: str) -> list[dict[str, Any]]:
    """Parse all JSON steps in one model turn (tool rounds + premature done)."""
    objects = extract_json_objects(raw)
    if objects:
        return objects
    return [parse_research_response(raw)]


def format_research_answer(text: str) -> str:
    """Normalize final /research text for Rich markdown display."""
    from ..llm import clean_model_text

    body = (text or "").strip()
    if not body:
        return ""

    if body.startswith("{") or '"action"' in body[:200]:
        try:
            for step in reversed(parse_research_steps(body)):
                answer = step.get("answer")
                if answer and str(answer).strip():
                    body = str(answer).strip()
                    break
        except (ValueError, json.JSONDecodeError):
            pass

    return clean_model_text(body)
