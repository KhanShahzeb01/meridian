"""Orchestrate compound prompts: context first, primary last."""

from __future__ import annotations

import re
from typing import Any

from .context_merge import merge_resolver_results
from .models import CompoundContext
from .ordering import build_execution_plan
from .parser import find_commands, is_compound_prompt
from .primary_dispatch import run_primary
from .resolvers.dispatch import resolve_context_step


def try_handle_compound_command(
    prompt: str,
    conversation: list,
    agent: Any,
    console: Any,
    manager: Any | None = None,
) -> bool:
    """
    Handle multi-command lines. Returns False to fall through to normal handle_command.
    """
    if not is_compound_prompt(prompt):
        return False

    commands = find_commands(prompt)
    plan = build_execution_plan(prompt, commands)
    if plan is None:
        return False

    _warn_unparsed_context_literals(console, plan)
    _print_plan(console, plan)

    results = []
    for step in plan.context_steps:
        console.print(
            f"[dim]Compound · resolving[/dim] [cyan]{step.name}[/cyan] …"
        )
        res = resolve_context_step(prompt, step, manager)
        for note in res.notes:
            console.print(f"[dim]  · {note}[/dim]")
        results.append(res)

    ctx = merge_resolver_results(results)
    if not ctx.tickers and not ctx.live_data_block:
        console.print(
            "[yellow]No data resolved from context commands "
            "(empty list, missing storage, or unrecognized context). "
            "Continuing with primary only.[/yellow]"
        )
    elif not ctx.tickers and ctx.live_data_block:
        console.print(
            "[dim]Context loaded with no tickers (empty list or message-only context).[/dim]"
        )

    return run_primary(
        plan,
        ctx,
        conversation=conversation,
        agent=agent,
        console=console,
        manager=manager,
    )


_UNPARSED_CONTEXT_RE = re.compile(
    r"/(?:watchlist|portfolio|quote|financials|earnings|news|peers|insider|holdings|sec|sector|index|macro|vix|screen|bundle)\b"
)


def _warn_unparsed_context_literals(console: Any, plan) -> None:
    """Warn when slash context tokens remain in the user intent (parse gap)."""
    if _UNPARSED_CONTEXT_RE.search(plan.user_intent):
        console.print(
            "[yellow]Some context slash commands were not parsed and may be missing "
            "from resolved data. Put each /watchlist or /portfolio on its own token "
            "(space or newline before it).[/yellow]"
        )


def _print_plan(console: Any, plan) -> None:
    steps = " → ".join(s.name for s in plan.context_steps)
    console.print(
        f"\n[bold magenta]Compound command[/bold magenta] "
        f"[dim]({steps} → {plan.primary.name})[/dim]"
    )
