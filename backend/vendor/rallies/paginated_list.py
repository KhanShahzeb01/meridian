"""Arrow-key paginated terminal views (10 rows per page)."""

from __future__ import annotations

from collections.abc import Callable
from io import StringIO
from typing import Any

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from rich.console import Console
from rich.table import Table

DEFAULT_PAGE_SIZE = 10


def total_pages(item_count: int, page_size: int = DEFAULT_PAGE_SIZE) -> int:
    if item_count <= 0:
        return 1
    return (item_count + page_size - 1) // page_size


def page_slice(items: list[Any], page: int, page_size: int = DEFAULT_PAGE_SIZE) -> list[Any]:
    if not items:
        return []
    pages = total_pages(len(items), page_size)
    page = max(0, min(page, pages - 1))
    start = page * page_size
    return items[start : start + page_size]


def render_ticker_table_page(
    rows: list[dict[str, str]],
    *,
    page: int,
    page_size: int = DEFAULT_PAGE_SIZE,
    title: str = "Tickers",
) -> str:
    """Rich table + footer as ANSI string for one page."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=100)
    chunk = page_slice(rows, page, page_size)
    pages = total_pages(len(rows), page_size)
    page = max(0, min(page, pages - 1))

    table = Table(title=title, title_style="bold cyan")
    table.add_column("Symbol", style="bright_green", no_wrap=True)
    table.add_column("Exchange", style="dim", no_wrap=True)
    table.add_column("Name")
    for row in chunk:
        table.add_row(
            row.get("symbol", ""),
            row.get("exchange", ""),
            (row.get("name") or "")[:60],
        )
    console.print(table)
    if not rows:
        console.print("[yellow]No tickers match this filter.[/yellow]")
    console.print(
        f"\n[dim]Page {page + 1}/{pages} · {len(rows)} symbol(s) · "
        f"← → or ↑ ↓ to change page · q or Esc to exit[/dim]"
    )
    return buf.getvalue()


def browse_rows_interactive(
    rows: list[dict[str, str]],
    *,
    title: str = "Tickers",
    page_size: int = DEFAULT_PAGE_SIZE,
    render_page: Callable[[list[dict[str, str]], int, int, str], str] | None = None,
) -> None:
    """
    Paginated browser: 10 rows per page, arrow keys to move, q/Esc to close.
    """
    if render_page is None:
        render_page = lambda items, page, size, t: render_ticker_table_page(
            items, page=page, page_size=size, title=t
        )

    state = {"page": 0}
    pages = total_pages(len(rows), page_size)

    def body() -> ANSI:
        text = render_page(rows, state["page"], page_size, title)
        return ANSI(text)

    control = FormattedTextControl(body)

    kb = KeyBindings()

    @kb.add("right")
    @kb.add("down")
    @kb.add("j")
    def _next(event) -> None:
        if state["page"] < pages - 1:
            state["page"] += 1
        event.app.invalidate()

    @kb.add("left")
    @kb.add("up")
    @kb.add("k")
    def _prev(event) -> None:
        if state["page"] > 0:
            state["page"] -= 1
        event.app.invalidate()

    @kb.add("home")
    def _first(event) -> None:
        state["page"] = 0
        event.app.invalidate()

    @kb.add("end")
    def _last(event) -> None:
        state["page"] = pages - 1
        event.app.invalidate()

    @kb.add("q")
    @kb.add("Q")
    @kb.add("escape")
    @kb.add("c-c")
    def _quit(event) -> None:
        event.app.exit()

    layout = Layout(Window(content=control, dont_extend_height=True))
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=False,
        mouse_support=False,
    )
    app.run()
