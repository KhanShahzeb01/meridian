"""LLM draft of memo template slots from collected data."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from ..skills.registry import get_skill
from ..tools import extract_json_objects
from .slots import MEMO_SLOT_KEYS

DRAFT_SYSTEM = """You are a buyside analyst writing a one-page investment memo.
You receive LIVE tool data only — never invent prices, multiples, or filing facts.

Respond with ONE JSON object (no markdown fence) whose keys fill the HTML template slots.
Use HTML fragments where noted (tables, <li> items). Use "we" voice. Steelman the bear case.

Required keys:
{ticker, direction, date, company_name, price_current, horizon, conviction,
 price_target_base, upside_pct, asymmetry, prob_weighted_return, variant_view,
 thesis_bullets, business_snapshot, whats_priced_in, scenario_table,
 bull_narrative, base_narrative, bear_narrative, catalysts_table, risks_table,
 position_management, monitoring_kpis, analyst, memo_guide}

Rules:
- memo_guide: 2–3 short HTML <p> paragraphs plus optional <ol> — how to read this memo,
  what the trade is, and the recommended section order (plain language, no filler)
- thesis_bullets: 3–5 <li> items, each ending with <em>Wrong if …</em>
- scenario_table: HTML <table> with Bull/Base/Bear rows (price, return %, probability)
- catalysts_table, risks_table: HTML tables with dates and observable tripwires
- monitoring_kpis: 4–6 <li> items
- valuation_analysis: 2–4 paragraphs on trailing P/E percentile, fair-value bands, DCF
  cross-check, and what the valuation facts imply for the trade (cite numbers from data)
- analyst: "Rallies Research"
- date: ISO date YYYY-MM-DD
- If DCF unavailable, say so in base_narrative; do not fabricate fair value
"""


def _default_slots(ticker: str, direction: str, horizon: str) -> dict[str, str]:
    today = date.today().isoformat()
    return {
        "ticker": ticker,
        "direction": direction,
        "date": today,
        "company_name": ticker,
        "price_current": "—",
        "horizon": horizon,
        "conviction": "medium",
        "price_target_base": "—",
        "upside_pct": "—",
        "asymmetry": "—",
        "prob_weighted_return": "—",
        "variant_view": "Variant view pending — insufficient structured data.",
        "thesis_bullets": "<li>See data appendix in research log.</li>",
        "business_snapshot": "Business snapshot unavailable.",
        "whats_priced_in": "Not available from tools.",
        "scenario_table": "<table><tr><th>Case</th><th>Target</th><th>Prob</th></tr></table>",
        "bull_narrative": "—",
        "base_narrative": "—",
        "bear_narrative": "—",
        "catalysts_table": "<table><tr><th>Date</th><th>Catalyst</th></tr></table>",
        "risks_table": "<table><tr><th>Risk</th><th>Tripwire</th></tr></table>",
        "position_management": "—",
        "monitoring_kpis": "<li>Re-run memo after earnings</li>",
        "analyst": "Rallies Research",
        "valuation_analysis": "Valuation analysis pending — see DCF and key metrics sections.",
        "memo_guide": "",
    }


def _parse_slots(raw: str) -> dict[str, str] | None:
    objects = extract_json_objects(raw)
    for obj in reversed(objects):
        if not isinstance(obj, dict):
            continue
        if "ticker" in obj or "variant_view" in obj:
            return {k: str(obj.get(k, "") or "") for k in MEMO_SLOT_KEYS}
    return None


def draft_memo_slots(
    llm: Any,
    *,
    ticker: str,
    direction: str,
    horizon: str,
    data_context: str,
    skill_text: str = "",
) -> dict[str, str]:
    defaults = _default_slots(ticker, direction.upper(), horizon)
    user = (
        f"Ticker: {ticker}\nDirection: {direction.upper()}\nHorizon: {horizon}\n\n"
        f"## Skill workflow\n{skill_text[:8000]}\n\n"
        f"## Live data\n{data_context[:100_000]}\n\n"
        "Return the JSON object with all template slots filled from the live data."
    )
    messages = [
        {"role": "system", "content": DRAFT_SYSTEM},
        {"role": "user", "content": user},
    ]
    raw = llm.prompt(messages, task_type="memo", no_cache=True)
    parsed = _parse_slots(str(raw))
    if not parsed:
        defaults["business_snapshot"] = (
            "Could not parse memo JSON from model; showing placeholders. "
            f"Raw excerpt: {str(raw)[:500]}"
        )
        return defaults
    merged = {**defaults, **parsed}
    merged["ticker"] = ticker.upper()
    merged["direction"] = direction.upper()
    merged.setdefault("date", date.today().isoformat())
    merged.setdefault("analyst", "Rallies Research")
    return merged


def load_write_memo_skill_text() -> str:
    skill = get_skill("write-memo")
    return skill.instructions if skill else ""
