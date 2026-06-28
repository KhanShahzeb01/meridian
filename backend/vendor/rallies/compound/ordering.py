"""Build execution order: all context steps before primary."""

from __future__ import annotations

from ..list_context import COMPOUND_CONTEXT_STOPWORDS
from ..portfolio_names import is_likely_portfolio_name
from ..watchlist_names import is_likely_watchlist_name
from .models import ExecutionPlan, ParsedCommand
from .registry import CONTEXT_PRIORITY, CommandRole, role_for_command

# Human-readable placeholders keep user intent intact when slash tokens are removed.
_CONTEXT_PLACEHOLDER_LABELS: dict[str, str] = {
    "/watchlist": "watchlist",
    "/portfolio": "portfolio holdings",
    "/quote": "quote data",
    "/financials": "financials",
    "/earnings": "earnings",
    "/news": "news",
    "/peers": "peers",
    "/insider": "insider activity",
    "/holdings": "holdings",
    "/sec": "SEC filings",
    "/sector": "sector data",
    "/index": "index data",
    "/macro": "macro data",
    "/vix": "VIX data",
    "/screen": "screen results",
    "/bundle": "bundle data",
}


def _placeholder_for_command(command_name: str) -> str:
    label = _CONTEXT_PLACEHOLDER_LABELS.get(command_name, command_name.lstrip("/"))
    return f"[{label}]"


def _sort_context_steps(steps: list[ParsedCommand]) -> tuple[ParsedCommand, ...]:
    """Context runs by dependency priority, not left-to-right in the sentence."""
    return tuple(
        sorted(
            steps,
            key=lambda s: (CONTEXT_PRIORITY.get(s.name, 500), s.start),
        )
    )


def build_execution_plan(raw_prompt: str, commands: list[ParsedCommand]) -> ExecutionPlan | None:
    stripped = raw_prompt.strip()
    if not commands:
        return None

    lead_offset = len(raw_prompt) - len(raw_prompt.lstrip())
    primary = commands[0]
    if primary.start != lead_offset:
        return None

    if role_for_command(primary.name) == CommandRole.SYSTEM:
        return None

    context_steps = [c for c in commands[1:] if role_for_command(c.name) == CommandRole.CONTEXT]
    if not context_steps:
        return None

    user_intent = _extract_user_intent(stripped, primary, context_steps)
    cleaned = _rebuild_primary_prompt(primary.name, user_intent)
    return ExecutionPlan(
        raw_prompt=raw_prompt,
        primary=primary,
        context_steps=_sort_context_steps(context_steps),
        cleaned_primary_prompt=cleaned,
        user_intent=user_intent,
    )


def _extract_user_intent(
    text: str,
    primary: ParsedCommand,
    embedded: list[ParsedCommand],
) -> str:
    """Replace embedded context commands with semantic placeholders; preserve grammar."""
    lead = len(text) - len(text.lstrip())
    parts: list[str] = []
    cursor = primary.end - lead
    for cmd in sorted(embedded, key=lambda c: c.start):
        local_start = cmd.start - lead
        local_end = cmd.end - lead
        if local_start < cursor:
            continue
        parts.append(text[cursor:local_start])
        parts.append(_placeholder_for_command(cmd.name))
        cursor = local_end
        cursor = _skip_context_list_name(text, cmd.name, cursor)
    parts.append(text[cursor:])
    return _normalize_intent_text("".join(parts))


def _rebuild_primary_prompt(primary_name: str, user_intent: str) -> str:
    intent = user_intent.strip()
    if not intent:
        return primary_name
    if intent.startswith(primary_name):
        return intent
    return f"{primary_name} {intent}"


def _normalize_intent_text(text: str) -> str:
    """Collapse horizontal whitespace; keep paragraph breaks for multiline prompts."""
    if "\n" in text:
        lines = [" ".join(line.split()) for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()
    return " ".join(text.split()).strip()


def _skip_context_list_name(text: str, command_name: str, cursor: int) -> int:
    """Skip optional list name token after /watchlist or /portfolio in compound lines."""
    if command_name not in ("/watchlist", "/portfolio"):
        return cursor
    remainder = text[cursor:]
    if not remainder or not remainder[0].isspace():
        return cursor
    stripped = remainder.lstrip()
    space_len = len(remainder) - len(stripped)
    token = stripped.split(None, 1)[0] if stripped else ""
    if not token or token.startswith("/") or token.lower() in COMPOUND_CONTEXT_STOPWORDS:
        return cursor
    is_name = (
        is_likely_watchlist_name(token)
        if command_name == "/watchlist"
        else is_likely_portfolio_name(token)
    )
    if is_name:
        return cursor + space_len + len(token)
    return cursor
