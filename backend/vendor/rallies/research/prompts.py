"""Canonical /research query templates."""

from __future__ import annotations

from rich.console import Console

DEFAULT_DEEP_DIVE_TICKER = "NVDA"


def build_deep_dive_research_prompt(ticker: str = DEFAULT_DEEP_DIVE_TICKER) -> str:
    """Full single-ticker prompt that drives skills + live tools in sequence."""
    sym = ticker.upper().strip()
    return (
        f"/research {sym} — full equity deep dive using Rallies skills and live tools only.\n\n"
        "Workflow:\n"
        f"1) load_skill edgartools, dcf-valuation, earnings-digest (and sec-risk-review if needed)\n"
        f"2) gather_equity_bundle({sym}) — quote, financials, margins, growth, news, analyst views\n"
        f"3) filing_section — business description, MD&A, and risk factors from latest 10-K/10-Q\n"
        "4) research_fetch — fill gaps (insider trades, recent earnings headlines, segment detail)\n"
        "5) run_dcf_quant for fair value / intrinsic value with sector-appropriate WACC; "
        "3×3 DCF sensitivity vs spot price\n"
        "6) If macro/rates matter for valuation, macro_snapshot (fed funds, yields, inflation)\n\n"
        "Deliver: business model & revenue drivers, competitive moat, financial quality "
        "(margins, FCF, balance sheet), recent news & filing catalysts, earnings beat/miss "
        "and guidance read-through, analyst sentiment from fetched data only, bull/base/bear scenarios, "
        "DCF vs market price verdict, top risks, and a clear conclusion. "
        "Cite only tool outputs — no invented numbers."
    )


def research_query_from_deep_dive_prompt(prompt: str) -> str:
    """Strip leading /research prefix for the research loop."""
    text = prompt.strip()
    if text.lower().startswith("/research "):
        return text[len("/research ") :].strip()
    return text


def print_research_usage(console: Console) -> None:
    """Usage panel when /research is invoked without a query."""
    example = build_deep_dive_research_prompt(DEFAULT_DEEP_DIVE_TICKER)
    console.print("[yellow]Usage: /research QUERY[/yellow]")
    console.print()
    console.print("[bold cyan]Recommended — full single-ticker deep dive[/bold cyan]")
    console.print(f"[dim]{example}[/dim]")
    console.print()
    console.print("[bold]Other examples[/bold]")
    console.print("[dim]/research compare AAPL and MSFT margins[/dim]")
    console.print("[dim]/research macro outlook: inflation, fed funds, and 10Y yield[/dim]")
    console.print()
    console.print(
        "[dim]Tip: replace NVDA with any ticker. Run /skill to preview workflows.[/dim]"
    )
