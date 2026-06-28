"""Orchestrate /memo: collect → enrich → experts → draft → write HTML."""

from __future__ import annotations

from typing import Any

from rich.markdown import Markdown
from rich.panel import Panel

from ..skills.actions import render_memo_template, write_memo_html
from .collect import collect_memo_data, pack_to_context_text
from .draft import draft_memo_slots, load_write_memo_skill_text
from .enrich import build_deterministic_slots
from .experts import collect_memo_expert_opinions
from .navigation import build_memo_navigation


def _chat_summary(slots: dict[str, str], meta: dict) -> str:
    ticker = slots.get("ticker", meta.get("ticker", ""))
    direction = slots.get("direction", meta.get("direction", ""))
    target = slots.get("price_target_base", "—")
    upside = slots.get("upside_pct", "—")
    asym = slots.get("asymmetry", "—")
    conv = slots.get("conviction", "—")
    path = meta.get("path", "")
    return (
        f"**{ticker}** · **{direction}** · Target **{target}** "
        f"({upside}) · Asymmetry **{asym}** · Conviction **{conv}**\n\n"
        f"Includes charts, DCF, expert panel, and references.\n\n"
        f"Memo saved to `{path}`"
    )


def run_memo_pipeline(
    ticker: str,
    direction: str,
    horizon: str,
    *,
    llm: Any,
    registry: Any,
    console: Any,
    manager: Any | None = None,
) -> bool:
    ticker = ticker.upper().strip()
    direction_label = "LONG" if direction.lower().startswith("l") else "SHORT"

    session = None
    agent = getattr(manager, "agent", None) if manager is not None else None
    if manager is not None:
        session = manager.begin_research_session(
            f"/memo {ticker} {direction_label} {horizon}"
        )

    console.print(
        f"\n[bold magenta]Investment memo[/bold magenta] — "
        f"[white]{ticker}[/white] [dim]{direction_label} · {horizon}[/dim]\n"
    )

    try:
        console.print(
            "[yellow]Step 1/5[/yellow] Gathering live data "
            "(bundle, MD&A, DCF, valuation)…"
        )
        pack = collect_memo_data(registry, ticker, console=console)
        context = pack_to_context_text(pack)
        if session:
            session.record_data_tool(
                "memo_collect",
                {"ticker": ticker},
                context[:12_000],
            )

        console.print("[yellow]Step 2/5[/yellow] Building charts & metrics tables…")
        deterministic = build_deterministic_slots(pack)

        console.print(
            "[yellow]Step 3/5[/yellow] Running expert panel "
            "(Buffett, Lynch, Simons)…"
        )
        expert_html = collect_memo_expert_opinions(
            ticker,
            llm,
            registry=registry,
            agent=agent,
            console=console,
        )
        deterministic["expert_opinions_section"] = expert_html
        if session:
            session.record_data_tool(
                "memo_experts",
                {"ticker": ticker},
                expert_html[:8000],
            )

        console.print("[yellow]Step 4/5[/yellow] Drafting narrative from skill + data…")
        skill_text = load_write_memo_skill_text()
        slots = draft_memo_slots(
            llm,
            ticker=ticker,
            direction=direction_label,
            horizon=horizon,
            data_context=context,
            skill_text=skill_text,
        )
        slots = {**slots, **deterministic}
        slots.update(build_memo_navigation(slots))
        if session:
            session.record_llm_tool(
                "memo_draft",
                {"ticker": ticker},
                str(slots)[:8000],
            )

        console.print("[yellow]Step 5/5[/yellow] Writing HTML…")
        html = render_memo_template(slots)
        if len(html) < 500:
            console.print("[red]Generated HTML too short — memo not saved.[/red]")
            return True

        meta = write_memo_html(ticker, direction_label, html)
        summary = _chat_summary(slots, meta)
        console.print(
            Panel(Markdown(summary), title="Memo", border_style="cyan")
        )
        if session:
            session.record_llm_tool(
                "memo_saved",
                {"path": meta.get("path")},
                summary,
            )
        return True
    except Exception as e:
        console.print(f"[red]Memo failed:[/red] {e}")
        return True
    finally:
        if manager is not None:
            manager.end_research_session()
