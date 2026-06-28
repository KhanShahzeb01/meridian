"""Slash command: /chart TICKER [timeframe]"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.markdown import Markdown
from rich.panel import Panel

from ..research.paths import rallies_data_dir
from .data import MetricSeries, build_pe_frame, slice_for_horizon
from .horizons import horizon_for_key, normalize_horizon, parse_horizons
from .summary import build_valuation_summary

DEFAULT_CHART_HORIZONS = ("5y",)


def _charts_dir() -> Path:
    path = rallies_data_dir() / "charts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_chart_args(prompt: str) -> dict:
    """Parse `/chart TICKER [ytd|1y|5y|10y|max] [--no-llm]`."""
    parts = prompt.strip().split()
    tickers: list[str] = []
    horizons: list[str] = []
    use_llm = True
    i = 1
    while i < len(parts):
        p = parts[i].lower()
        if p in ("--no-llm", "--facts-only"):
            use_llm = False
            i += 1
            continue
        if normalize_horizon(p):
            horizons.append(p)
            i += 1
            continue
        if p.isalpha() and 1 <= len(p) <= 6:
            tickers.append(p.upper())
            i += 1
            continue
        i += 1
    return {
        "tickers": tickers,
        "horizons": horizons,
        "use_llm": use_llm,
    }


def _series_for_horizon(base: MetricSeries, horizon) -> MetricSeries:
    sliced = MetricSeries(
        base.ticker,
        "valuation",
        horizon,
        base.frame.copy(),
        base.company_name,
        market=base.market,
    )
    sliced.frame = slice_for_horizon(sliced)
    return sliced


def _print_chart_saved(console, html_path: Path, opened: bool) -> None:
    uri = html_path.resolve().as_uri()
    if opened:
        console.print(
            Panel.fit(
                f"[green]Chart saved — opened in browser[/green]\n[dim]{html_path}[/dim]",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel.fit(
                f"[green]Chart saved[/green]\n"
                f"[dim]HTML: {html_path}[/dim]\n"
                f"[yellow]Could not launch a browser.[/yellow] Open manually:\n"
                f"  google-chrome '{uri}'\n"
                f"[dim]Or: export RALLIES_BROWSER=google-chrome[/dim]",
                border_style="green",
            )
        )


def _print_valuation_analysis(
    console,
    series: MetricSeries,
    *,
    agent=None,
    use_llm: bool = True,
) -> None:
    llm = getattr(agent, "llm", None) if agent is not None else None
    if use_llm and llm is not None:
        from .llm_summary import build_llm_valuation_summary

        console.print("[dim]Generating detailed valuation analysis (LLM)…[/dim]")
        text = build_llm_valuation_summary(series, llm)
        console.print(Panel(Markdown(text), title="Valuation analysis", border_style="cyan"))
        return

    text = build_valuation_summary(series)
    title = "Valuation summary"
    if use_llm and llm is None:
        title = "Valuation summary (structured — start session with LLM for narrative)"
    console.print(Panel(text, title=title, border_style="cyan"))


def _default_horizons(user_horizons: list[str]) -> list:
    if user_horizons:
        return parse_horizons(user_horizons)
    return [horizon_for_key(k) for k in DEFAULT_CHART_HORIZONS]


def handle_chart_command(prompt: str, console, agent=None) -> bool:
    args = parse_chart_args(prompt)
    tickers = args["tickers"]
    use_llm = args["use_llm"]

    if not tickers:
        console.print(
            "[yellow]Usage:[/yellow] /chart TICKER [ytd 1y 5y 10y max]\n"
            "[dim]Example: /chart NVDA 5y[/dim]\n\n"
            "[bold]Opens[/bold] a Plotly valuation dashboard in the browser:\n"
            "  • Fair value vs price\n"
            "  • Price vs trailing EPS\n"
            "  • Trailing P/E with median & percentile band\n"
            "  • Trailing vs forward P/E and analyst targets\n"
            "[dim]Optional: --no-llm — skip LLM narrative[/dim]"
        )
        return True

    try:
        import pandas  # noqa: F401
    except ImportError:
        console.print("[red]pandas required.[/red] pip install 'rallies[viz]'")
        return True

    try:
        import plotly  # noqa: F401
    except ImportError:
        console.print("[red]plotly required.[/red] pip install 'rallies[viz]'")
        return True

    out_dir = _charts_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    horizon_list = _default_horizons(args["horizons"])

    if len(tickers) >= 2:
        return _handle_comparison(
            tickers,
            horizon_list,
            out_dir,
            stamp,
            console,
            agent=agent,
            use_llm=use_llm,
        )

    ticker = tickers[0]
    console.print(
        f"\n[yellow]Building valuation dashboard[/yellow] — {ticker} "
        f"({len(horizon_list)} window(s))…"
    )
    try:
        base = build_pe_frame(ticker, horizon_for_key("max"))
    except ImportError as e:
        console.print(f"[red]{e}[/red]")
        return True
    except Exception as e:
        console.print(f"[red]Could not load data:[/red] {e}")
        return True

    if base.frame.empty:
        console.print("[red]No valuation data for this ticker.[/red]")
        return True

    from .dashboard_plotly import open_valuation_dashboard

    for horizon in horizon_list:
        try:
            series = _series_for_horizon(base, horizon)
            if series.frame.empty:
                console.print(f"[red]No data for {horizon.key}.[/red]")
                continue

            console.print(
                f"[dim]{horizon.label}: {series.frame.index.min().date()} → "
                f"{series.frame.index.max().date()} ({len(series.frame)} points)[/dim]"
            )

            html_path = out_dir / f"{ticker}_valuation_{horizon.key}_{stamp}.html"
            _, opened = open_valuation_dashboard(
                series,
                html_path,
                open_browser=True,
            )
            _print_chart_saved(console, html_path, opened)
            _print_valuation_analysis(
                console, series, agent=agent, use_llm=use_llm
            )

        except Exception as e:
            console.print(f"[red]Dashboard failed ({horizon.key}):[/red] {e}")
            continue

    return True


def _handle_comparison(
    tickers: list[str],
    horizon_list,
    out_dir: Path,
    stamp: str,
    console,
    *,
    agent=None,
    use_llm: bool = True,
) -> bool:
    from .compare import build_comparison_snapshots
    from .compare_plotly import open_comparison_chart
    from .summary import build_comparison_table

    hkey = horizon_list[0].key if horizon_list else "5y"
    console.print(
        f"\n[yellow]Loading trailing snapshots for {', '.join(tickers)}[/yellow] ({hkey})…"
    )
    try:
        snaps = build_comparison_snapshots(tickers[:5], horizon_key=hkey)
        if not snaps:
            console.print("[red]No comparison data.[/red]")
            return True

        html_path = out_dir / f"{'_'.join(tickers[:3])}_compare_{hkey}_{stamp}.html"
        hlabel = horizon_list[0].label if horizon_list else hkey
        _, opened = open_comparison_chart(
            snaps,
            html_path,
            horizon_label=hlabel,
            open_browser=True,
        )
        _print_chart_saved(console, html_path, opened)
        console.print(Panel(build_comparison_table(snaps), title="Summary table", border_style="cyan"))

        llm = getattr(agent, "llm", None) if agent is not None else None
        if use_llm and llm is not None:
            from .llm_summary import build_llm_comparison_summary

            console.print("[dim]Generating comparison analysis (LLM)…[/dim]")
            text = build_llm_comparison_summary(snaps, hlabel, llm)
            console.print(Panel(Markdown(text), title="Comparison analysis", border_style="cyan"))
    except Exception as e:
        console.print(f"[red]Comparison chart failed:[/red] {e}")
    return True
