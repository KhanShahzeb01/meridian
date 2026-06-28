"""LLM-generated detailed valuation narrative from chart facts."""

from __future__ import annotations

from typing import Any

from ..llm import LLMError
from .facts import (
    build_comparison_facts,
    build_valuation_facts,
    format_facts_for_llm,
)
from .data import MetricSeries
from .summary import build_valuation_summary

_SYSTEM = """You are a senior equity research analyst writing for an informed retail investor.

You receive structured trailing valuation data from automated charts (P/E, EPS, PEG, fair-value bands).
Rules:
- Use ONLY numbers present in the data block. Do not invent prices, multiples, or growth rates.
- If forward estimates are provided, contrast them with trailing metrics and explain the gap.
- Resolve apparent contradictions (e.g. low P/E vs history but high PEG) using the growth fields provided.
- Reference chart panels A–G when helpful (F: trailing vs forward P/E, G: analyst targets).
- Write in clear markdown: ## section headers, short paragraphs, bullet lists where useful.
- Do NOT use Rich/console markup like [bold] or [cyan].
- Length: thorough but focused (about 500–900 words).
- End with a short "Key risks & limits" section mentioning data caveats from warnings if any.
"""

_COMPARISON_SYSTEM = """You are a senior equity research analyst comparing multiple stocks on trailing valuation metrics.

Use ONLY the provided snapshot table. Write markdown with ## headers.
Compare P/E, PEG, growth, and forward metrics where available.
Recommend no buy/sell — analytical comparison only.
About 400–700 words."""


def _messages(system: str, user_body: str) -> list[dict]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_body},
    ]


def build_llm_valuation_summary(series: MetricSeries, llm: Any) -> str:
    facts = build_valuation_facts(series)
    if facts.get("error"):
        return build_valuation_summary(series)

    user = (
        f"Write a detailed valuation analysis for {series.company_name} ({series.ticker}).\n\n"
        f"STRUCTURED DATA (authoritative):\n```json\n{format_facts_for_llm(facts)}\n```"
    )
    try:
        return llm.prompt(_messages(_SYSTEM, user), task_type="answer").strip()
    except LLMError as e:
        fallback = build_valuation_summary(series)
        return (
            f"{e.user_message()}\n\n"
            "---\n\n"
            "**Structured summary (LLM unavailable):**\n\n"
            f"{fallback}"
        )
    except Exception as e:
        fallback = build_valuation_summary(series)
        return f"Analysis unavailable ({e}).\n\n{fallback}"


def build_llm_comparison_summary(
    snapshots: list[dict],
    horizon_label: str,
    llm: Any,
) -> str:
    facts = build_comparison_facts(snapshots, horizon_label)
    tickers = ", ".join(s["ticker"] for s in snapshots)
    user = (
        f"Compare trailing valuation for: {tickers}\n\n"
        f"STRUCTURED DATA:\n```json\n{format_facts_for_llm(facts)}\n```"
    )
    try:
        return llm.prompt(_messages(_COMPARISON_SYSTEM, user), task_type="answer").strip()
    except LLMError as e:
        return f"{e.user_message()}\n\nUse the summary table above for raw figures."
