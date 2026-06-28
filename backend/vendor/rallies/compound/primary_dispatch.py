"""Run the primary slash handler after context is resolved."""

from __future__ import annotations

from typing import Any

from .models import CompoundContext, ExecutionPlan


def run_primary(
    plan: ExecutionPlan,
    ctx: CompoundContext,
    *,
    conversation: list,
    agent: Any,
    console: Any,
    manager: Any | None,
) -> bool:
    """Dispatch to existing handlers; returns True if handled."""
    name = plan.primary.name
    if name == "/research":
        return _run_research(plan, ctx, agent, console, manager, conversation)

    prompt = plan.effective_primary_prompt(ctx)
    if name == "/ask":
        return _run_ask(prompt, ctx, agent, console, manager, conversation)
    if name == "/debate":
        return _run_debate(prompt, ctx, agent, console, manager, conversation)
    if name == "/consensus":
        return _run_consensus(prompt, ctx, agent, console, manager, conversation)
    if name == "/memo":
        return _run_memo(prompt, ctx, agent, console, manager)

    console.print(
        f"[yellow]Compound primary {name} is not wired yet.[/yellow]\n"
        "[dim]Supported primaries: /ask, /debate, /research, /consensus, /memo[/dim]"
    )
    return True


def _attach_context(manager: Any | None, ctx: CompoundContext) -> None:
    if manager is not None:
        manager.compound_context = ctx


def _detach_context(manager: Any | None) -> None:
    if manager is not None and hasattr(manager, "compound_context"):
        delattr(manager, "compound_context")


def _run_ask(
    prompt: str, ctx: CompoundContext, agent, console, manager, conversation: list
) -> bool:
    from ..helpers import handle_ask_command

    _attach_context(manager, ctx)
    try:
        return handle_ask_command(
            prompt, agent, console, manager=manager, conversation=conversation
        )
    finally:
        _detach_context(manager)


def _run_debate(
    prompt: str, ctx: CompoundContext, agent, console, manager, conversation: list
) -> bool:
    from ..helpers import handle_debate_command

    _attach_context(manager, ctx)
    try:
        return handle_debate_command(
            prompt, agent, console, manager=manager, conversation=conversation
        )
    finally:
        _detach_context(manager)


def _run_research(
    plan: ExecutionPlan,
    ctx: CompoundContext,
    agent,
    console,
    manager,
    conversation: list,
) -> bool:
    from ..research.commands import handle_research_command

    base_prompt = plan.cleaned_primary_prompt
    parts = base_prompt.strip().split(None, 1)
    if len(parts) < 2:
        return handle_research_command(
            base_prompt, console, manager, agent, conversation
        )

    query = plan.user_intent.strip() or parts[1].strip()
    augmented = ctx.augment_query(query)
    wrapped = f"/research {augmented}"

    _attach_context(manager, ctx)
    try:
        return handle_research_command(wrapped, console, manager, agent, conversation)
    finally:
        _detach_context(manager)


def _run_consensus(
    prompt: str, ctx: CompoundContext, agent, console, manager, conversation: list
) -> bool:
    from ..helpers import handle_consensus_command

    # Tickers come from compound_context in handle_consensus_command (batched if >6).
    rebuilt = prompt

    _attach_context(manager, ctx)
    try:
        return handle_consensus_command(
            rebuilt, agent, console, manager=manager, conversation=conversation
        )
    finally:
        _detach_context(manager)


def _run_memo(prompt: str, ctx: CompoundContext, agent, console, manager) -> bool:
    from ..research.commands import handle_memo_command

    _attach_context(manager, ctx)
    try:
        return handle_memo_command(prompt, console, manager, agent)
    finally:
        _detach_context(manager)
