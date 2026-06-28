"""
Registry of rallies data-fetch capabilities (additive observability layer).

Used for planner/action prompt hints and scratchpad tool naming — does not replace
slash commands or the existing planner JSON flow.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    compact_description: str
    concurrency_safe: bool = True


# Mirrors rallies source routing in agent._get_real_data (Wave 1).
REGISTERED_TOOLS: list[RegisteredTool] = [
    RegisteredTool(
        name="fred_macro",
        description=(
            "Fetch macroeconomic indicators from FRED (Fed funds, CPI, unemployment, "
            "10Y Treasury, GDP). Use when the step mentions economy, rates, inflation, or Fed."
        ),
        compact_description="FRED macro indicators (rates, CPI, unemployment, GDP).",
    ),
    RegisteredTool(
        name="hedgefund_snapshot",
        description=(
            "Fetch hedge fund monitor snapshot (leverage, positioning). "
            "Use for institutional / hedge fund / fund flow questions."
        ),
        compact_description="OFR hedge fund monitor snapshot.",
    ),
    RegisteredTool(
        name="cboe_vix",
        description="Fetch CBOE VIX level and change. Use for volatility / fear index questions.",
        compact_description="CBOE VIX index.",
    ),
    RegisteredTool(
        name="yfinance_quote",
        description=(
            "Live quote: price, P/E, market cap, sector. Use when tickers need current market data."
        ),
        compact_description="Yahoo Finance quote for one or more tickers.",
    ),
    RegisteredTool(
        name="yfinance_financials",
        description=(
            "Income statement highlights (revenue, net income) from Yahoo Finance. "
            "Use for financials / earnings / margin steps."
        ),
        compact_description="Yahoo Finance financial statement rows.",
    ),
    RegisteredTool(
        name="edgartools_insider",
        description=(
            "Recent Form 4 insider trades via SEC EDGAR. "
            "Use for insider buying/selling / executive trade questions."
        ),
        compact_description="EDGAR insider (Form 4) activity.",
    ),
    RegisteredTool(
        name="finnhub_news",
        description="Recent company news headlines from Finnhub. Use for news / headline steps.",
        compact_description="Finnhub company news headlines.",
    ),
    RegisteredTool(
        name="edgartools_sec_filings",
        description=(
            "Recent SEC filings (8-K by default) via EDGAR. "
            "Fetched in parallel with quotes for single-ticker steps."
        ),
        compact_description="EDGAR recent filings list.",
    ),
    RegisteredTool(
        name="web_fetch",
        description=(
            "Fetch a public URL and convert HTML to markdown (cached under .rallies/web-fetch-cache). "
            "Use for investor relations pages, press releases, or primary sources. "
            "Slash command: /fetch URL."
        ),
        compact_description="HTTP fetch URL → markdown (IR pages, docs).",
    ),
    RegisteredTool(
        name="parallel_ticker_bundle",
        description=(
            "Concurrent read-only fetch: yfinance quote + EDGAR recent filings for one ticker."
        ),
        compact_description="Parallel quote + SEC bundle (single ticker).",
    ),
    RegisteredTool(
        name="research_fetch",
        description=(
            "Meta-tool: NL intent routes to quote, financials/margins, news, insider, "
            "macro, or filing sources. Primary tool for /research compare questions."
        ),
        compact_description="NL router over rallies quote/financials/filing sources.",
    ),
    RegisteredTool(
        name="filing_section",
        description=(
            "Read SEC filing sections via edgartools (risk factors, MD&A, business). "
            "Slash command: /filing TICKER section."
        ),
        compact_description="EDGAR section text (10-K / 10-Q items).",
    ),
    RegisteredTool(
        name="load_skill",
        description="Load a SKILL.md workflow checklist (e.g. dcf-valuation). Slash: /skill NAME.",
        compact_description="SKILL.md guided workflow loader.",
    ),
    RegisteredTool(
        name="run_dcf_quant",
        description="Run quant DCF engine (same as /dcf) from research/memo skills.",
        compact_description="Programmatic /dcf for research loop.",
    ),
    RegisteredTool(
        name="gather_equity_bundle",
        description="One-shot quote + financials + news + SEC + filing excerpts for memos.",
        compact_description="Equity data bundle for write-memo / earnings-digest.",
    ),
    RegisteredTool(
        name="write_memo_html",
        description="Write investment memo HTML to .rallies/memos/.",
        compact_description="Persist memo HTML (write-memo skill).",
    ),
    RegisteredTool(
        name="spawn_subagent",
        description="Delegate isolated sub-task inside /research (max 3 parallel).",
        compact_description="Parallel subagent workers in /research only.",
        concurrency_safe=False,
    ),
    RegisteredTool(
        name="research_compaction",
        description="LLM summarization of tool history when /research context is large.",
        compact_description="Full compaction in /research (Wave 4).",
        concurrency_safe=False,
    ),
    RegisteredTool(
        name="research_llm",
        description="Research mode LLM iteration (/research tool loop).",
        compact_description="Dexter-style /research agent loop.",
        concurrency_safe=False,
    ),
    RegisteredTool(
        name="persona_llm",
        description="Persona analysis LLM call (/ask, /debate). Not a market data tool.",
        compact_description="Advanced persona LLM response (/ask).",
        concurrency_safe=False,
    ),
    RegisteredTool(
        name="planner_llm",
        description="Planning LLM call that emits JSON research steps.",
        compact_description="Planner step generation.",
        concurrency_safe=False,
    ),
    RegisteredTool(
        name="action_llm",
        description="Action LLM call that synthesizes findings for one plan step.",
        compact_description="Per-step action synthesis.",
        concurrency_safe=False,
    ),
]

_TOOL_MAP = {t.name: t for t in REGISTERED_TOOLS}


def get_tool(name: str) -> RegisteredTool | None:
    return _TOOL_MAP.get(name)


def build_compact_tool_descriptions() -> str:
    lines = [f"- **{t.name}**: {t.compact_description}" for t in REGISTERED_TOOLS]
    return "\n".join(lines)


def build_tool_descriptions_section() -> str:
    blocks = []
    for t in REGISTERED_TOOLS:
        blocks.append(f"### {t.name}\n{t.description}")
    return "\n\n".join(blocks)
