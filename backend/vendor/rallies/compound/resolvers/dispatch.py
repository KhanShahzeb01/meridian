"""Route a context command name to its resolver."""

from __future__ import annotations

from typing import Any

from ..models import ParsedCommand
from .base import ResolverResult
from .portfolio import resolve_portfolio
from .ticker_arg import resolve_financials, resolve_quote
from .watchlist import resolve_watchlist


def resolve_context_step(
    prompt: str,
    step: ParsedCommand,
    manager: Any | None,
) -> ResolverResult:
    name = step.name
    if name == "/watchlist":
        return resolve_watchlist(manager, prompt, command_end=step.end)
    if name == "/portfolio":
        return resolve_portfolio(manager, prompt, command_end=step.end)
    if name == "/quote":
        return resolve_quote(prompt, step, manager)
    if name == "/financials":
        return resolve_financials(prompt, step, manager)
    return ResolverResult(
        source=name.lstrip("/"),
        notes=[f"Context command {name} is not wired yet — skipped."],
    )
