"""Subagent types and tool allowlists (Wave 4 rank 17)."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_SUBAGENT_TYPE = "research"
MAX_SUBAGENTS_PER_ROUND = 3
DEFAULT_SUBAGENT_MAX_ITERATIONS = 5


@dataclass(frozen=True)
class SubagentTypeConfig:
    name: str
    description: str
    allowed_tools: frozenset[str]
    max_iterations: int


SUBAGENT_TYPES: dict[str, SubagentTypeConfig] = {
    "research": SubagentTypeConfig(
        name="research",
        description="Web + filings + quotes for one focused question.",
        allowed_tools=frozenset(
            {"research_fetch", "research_fetch_multi", "filing_section", "web_fetch"}
        ),
        max_iterations=DEFAULT_SUBAGENT_MAX_ITERATIONS,
    ),
    "analysis": SubagentTypeConfig(
        name="analysis",
        description="Financials, DCF, and bundles for one ticker or comparison.",
        allowed_tools=frozenset(
            {
                "research_fetch",
                "research_fetch_multi",
                "run_dcf_quant",
                "gather_equity_bundle",
                "filing_section",
            }
        ),
        max_iterations=DEFAULT_SUBAGENT_MAX_ITERATIONS,
    ),
}


def resolve_subagent_type(name: str | None) -> SubagentTypeConfig:
    key = (name or DEFAULT_SUBAGENT_TYPE).strip().lower()
    return SUBAGENT_TYPES.get(key, SUBAGENT_TYPES[DEFAULT_SUBAGENT_TYPE])
