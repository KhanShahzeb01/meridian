"""Load and display compound-command documentation in the terminal."""

from __future__ import annotations

from pathlib import Path

from rich.markdown import Markdown
from rich.panel import Panel

_COMPOUND_HELP_FILE = Path(__file__).resolve().parent / "COMPOUND_HELP.md"


def compound_help_path() -> Path:
    return _COMPOUND_HELP_FILE


def show_compound_help(console) -> bool:
    """Render COMPOUND_HELP.md with Rich Markdown inside a panel."""
    path = compound_help_path()
    if not path.is_file():
        console.print(f"[red]Compound help file not found:[/red] {path}")
        return True

    body = path.read_text(encoding="utf-8").strip()
    console.print()
    console.print(
        Panel(
            Markdown(body),
            title="[bold bright_magenta]Compound slash commands[/bold bright_magenta]",
            subtitle="[dim]Context first · primary last · one line[/dim]",
            border_style="bright_magenta",
            padding=(1, 2),
        )
    )
    console.print(
        "[dim]Tip: /ask munger pick 5 /watchlist watchlist_khan  ·  "
        "/research rebalance /portfolio portfolio_2025  ·  "
        "Reload: /compound_help[/dim]\n"
    )
    return True
