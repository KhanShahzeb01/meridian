"""Slash-command handlers for Wave 2–3 research features."""

from __future__ import annotations

from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table


def handle_fetch_command(prompt: str, console) -> bool:
    parts = prompt.strip().split(None, 1)
    if len(parts) < 2:
        console.print("[yellow]Usage: /fetch URL[/yellow]")
        console.print("[dim]Example: /fetch https://investor.apple.com/[/dim]")
        return True

    url = parts[1].strip()
    from .web import fetch_url

    console.print(f"[yellow]Fetching[/yellow] {url} …")
    try:
        result = fetch_url(url)
    except ValueError as e:
        console.print(f"[red]Invalid URL:[/red] {e}")
        return True
    except Exception as e:
        console.print(f"[red]Fetch failed:[/red] {e}")
        return True

    title = result.get("title") or result.get("url", url)
    cached = result.get("cached", False)
    truncated = result.get("truncated", False)
    meta = []
    if cached:
        meta.append("cache hit")
    if truncated:
        meta.append("truncated")
    meta_str = f" ({', '.join(meta)})" if meta else ""
    body = result.get("markdown", "")
    console.print(
        Panel(
            Markdown(body[:120_000] if body else "_empty body_"),
            title=f"Web fetch — {title}{meta_str}",
            border_style="cyan",
        )
    )
    cache_dir = result.get("url", url)
    console.print(f"[dim]Cache key under .rallies/web-fetch-cache/ for {cache_dir}[/dim]")
    return True


def handle_soul_command(console) -> bool:
    from .soul import ensure_default_soul_template, load_soul, soul_path

    ensure_default_soul_template()
    path = soul_path()
    soul = load_soul()
    console.print(f"[bold cyan]Research SOUL[/bold cyan] [dim]({path})[/dim]\n")
    if soul:
        console.print(Panel(soul, border_style="magenta"))
    else:
        console.print(
            "[yellow]No SOUL yet. Edit the file above to set tone and voice for research.[/yellow]"
        )
    return True


def handle_bundle_command(prompt: str, console, manager) -> bool:
    """Diagnostic: parallel quote + SEC for one ticker."""
    parts = prompt.strip().split(None, 1)
    if len(parts) < 2:
        console.print("[yellow]Usage: /bundle TICKER[/yellow]")
        return True
    ticker = parts[1].upper().strip().split()[0]
    registry = getattr(manager, "data_registry", None) if manager else None
    if registry is None:
        console.print("[red]Data registry unavailable.[/red]")
        return True

    from .batch import bundle_to_text, parallel_quote_sec_bundle

    console.print(
        "[dim]Wave 2 diagnostic: same parallel fetch used during research for a single ticker "
        "(Yahoo quote + recent 8-K list). Not a trade recommendation.[/dim]"
    )
    console.print(f"[yellow]Parallel fetch[/yellow] quote + SEC for {ticker} …")
    records = parallel_quote_sec_bundle(registry, ticker)
    if not records:
        console.print(
            "[yellow]No data returned. Install market sources in this environment:[/yellow]\n"
            "[cyan]pip install 'rallies[sources]'[/cyan]  (yfinance + edgartools)"
        )
        return True
    text = bundle_to_text(records)
    console.print(Panel(text or "[dim]No data returned[/dim]", title=f"Bundle — {ticker}", border_style="green"))
    return True


def handle_skill_command(prompt: str, console) -> bool:
    parts = prompt.strip().split(None, 1)
    from .skills import discover_skills, get_skill

    if len(parts) < 2:
        skills = discover_skills()
        console.print("[bold cyan]Research skills[/bold cyan] (.rallies/skills/ overrides builtin)\n")
        if not skills:
            console.print("[yellow]No skills found.[/yellow]")
            return True
        table = Table(show_header=True, header_style="bold")
        table.add_column("Name")
        table.add_column("Source")
        table.add_column("Description")
        for s in skills:
            table.add_row(s.name, s.source, s.description[:80])
        console.print(table)
        console.print("\n[dim]Usage: /skill NAME — e.g. /skill dcf-valuation[/dim]")
        return True

    name = parts[1].strip().split()[0]
    skill = get_skill(name)
    if not skill:
        console.print(f"[red]Skill not found:[/red] {name}")
        console.print("[dim]Run /skill to list available workflows.[/dim]")
        return True

    console.print(
        Panel(
            Markdown(skill.instructions[:120_000]),
            title=f"Skill — {skill.name} ({skill.source})",
            border_style="magenta",
        )
    )
    console.print(f"[dim]{skill.path}[/dim]")
    return True


def handle_filing_command(prompt: str, console, manager) -> bool:
    parts = prompt.strip().split(None, 2)
    if len(parts) < 2:
        console.print("[yellow]Usage: /filing TICKER [section query][/yellow]")
        console.print("[dim]Example: /filing AAPL risk factors[/dim]")
        return True

    ticker = parts[1].upper().strip()
    section_query = parts[2].strip() if len(parts) > 2 else "risk factors"
    from .filing import fetch_filing_section, format_filing_section

    console.print(f"[yellow]Fetching[/yellow] {ticker} filing — {section_query} …")
    result = fetch_filing_section(ticker, section_query)
    text = format_filing_section(result)
    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        return True
    console.print(
        Panel(
            Markdown(text[:120_000]),
            title=f"Filing — {ticker}",
            border_style="cyan",
        )
    )
    if manager and getattr(manager, "research_session", None):
        manager.research_session.record_data_tool(
            "filing_section",
            {"ticker": ticker, "section": section_query},
            text[:8000],
        )
    return True


def handle_research_command(
    prompt: str,
    console,
    manager,
    agent,
    conversation: list | None = None,
) -> bool:
    from .prompts import print_research_usage

    parts = prompt.strip().split(None, 1)
    if len(parts) < 2:
        print_research_usage(console)
        return True

    query = parts[1].strip()
    if not query:
        print_research_usage(console)
        return True

    registry = getattr(manager, "data_registry", None) if manager else None
    if registry is None:
        console.print("[red]Data registry unavailable.[/red]")
        return True

    from ..graph.flags import graph_memory_enabled
    from ..graph.research.dispatch import run_research_for_command
    from ..graph.research.state_slice import rallies_slice_from_manager
    from ..graph.research.tool_callback import attach_memory_callback_for_loop
    from .loop import ResearchLoop
    from .progress import ResearchProgress
    from .tools import format_research_answer

    convo = list(conversation or [])

    try:
        from rich.live import Live
        from rich.spinner import Spinner
    except ImportError:
        Live = None
        Spinner = None

    session = None
    if manager:
        session = manager.begin_research_session(query, convo)
    elif agent:
        from .session import ResearchSession

        session = ResearchSession.begin(query)
        agent.set_research_session(session)

    progress = ResearchProgress(console=console)
    loop = ResearchLoop(
        agent.llm if agent else manager.agent.llm,
        registry,
        session=session,
        progress=progress,
    )
    if graph_memory_enabled():
        entities, memory, _input = rallies_slice_from_manager(manager, query, convo)
        attach_memory_callback_for_loop(loop, entities=entities, memory=memory)

    console.print()
    try:
        if Live is not None and Spinner is not None:
            spinner = Spinner("dots", text="[bright_magenta]Researching...[/bright_magenta]")
            with Live(spinner, console=console, refresh_per_second=10):
                answer = run_research_for_command(
                    loop,
                    query,
                    manager=manager,
                    console=console,
                    conversation=convo,
                )
        else:
            answer = run_research_for_command(
                loop,
                query,
                manager=manager,
                console=console,
                conversation=convo,
            )
    finally:
        if manager:
            manager.end_research_session()
        elif agent and session:
            agent.set_research_session(None)

    answer = format_research_answer(answer)
    if not str(answer).strip():
        console.print(
            "[yellow]The model returned an empty research answer. "
            "Try again or check /research-log.[/yellow]"
        )
        return True

    console.print(Panel(Markdown(answer), title="Response", border_style="cyan"))
    if manager is not None and convo is not None:
        from ..thread_memory import record_command_turn

        history = getattr(manager, "history_session", None)
        session_id = (
            str(history.get("id") or "")
            if isinstance(history, dict)
            else ""
        ) or None
        record_command_turn(
            convo,
            user_query=prompt.strip(),
            assistant_answer=answer,
            session_id=session_id,
        )
    return True


def handle_memo_command(prompt: str, console, manager, agent) -> bool:
    """Shortcut: /memo TICKER long|short → dedicated memo pipeline (collect, draft, HTML)."""
    parts = prompt.strip().split()
    if len(parts) < 3:
        console.print("[yellow]Usage: /memo TICKER long|short [horizon][/yellow]")
        console.print("[dim]Example: /memo AAPL long 12mo[/dim]")
        console.print(
            "[dim]Writes rich HTML to .rallies/memos/ "
            "(charts, DCF, expert panel, references).[/dim]"
        )
        return True

    ticker = parts[1].upper()
    direction = parts[2].lower()
    if direction not in ("long", "short", "l", "s"):
        console.print("[yellow]Direction must be long or short[/yellow]")
        return True
    horizon = parts[3] if len(parts) > 3 else "12mo"

    registry = getattr(manager, "data_registry", None) if manager else None
    if registry is None:
        console.print("[red]Data registry unavailable.[/red]")
        return True

    llm = getattr(agent, "llm", None) if agent else None
    if llm is None and manager is not None:
        mgr_agent = getattr(manager, "agent", None)
        if mgr_agent is not None:
            llm = getattr(mgr_agent, "llm", None)
    if llm is None:
        console.print("[red]LLM unavailable for memo drafting.[/red]")
        return True

    from .memo import run_memo_pipeline

    return run_memo_pipeline(
        ticker,
        direction,
        horizon,
        llm=llm,
        registry=registry,
        console=console,
        manager=manager,
    )
