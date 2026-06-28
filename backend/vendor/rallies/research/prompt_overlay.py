"""Combine RULES + SOUL overlays for planner/action/research prompts."""

from __future__ import annotations

from .rules import rules_system_prefix
from .soul import soul_system_prefix


def research_system_prefix(
    *,
    include_rules: bool = True,
    include_soul: bool = True,
) -> str:
    parts: list[str] = []
    if include_rules:
        rules = rules_system_prefix()
        if rules:
            parts.append(rules.strip())
    if include_soul:
        soul = soul_system_prefix()
        if soul:
            parts.append(soul.strip())
    return "\n\n".join(parts) + ("\n\n" if parts else "")
