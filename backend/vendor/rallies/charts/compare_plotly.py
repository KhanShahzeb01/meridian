"""Plotly multi-ticker comparison — notebook sector charts + responsive layout."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from .browser import open_html_file
from .notebook_charts import build_sector_comparison_figure
from .plotly_layout import write_responsive_html


def comparison_banner_title(
    snapshots: list[dict],
    *,
    horizon_label: str = "",
) -> str:
    tickers = ", ".join(s["ticker"] for s in snapshots)
    title = f"{tickers} Valuation Comparison"
    if horizon_label:
        return f"{title} · {horizon_label}"
    return title


def build_comparison_figure(
    snapshots: list[dict],
    *,
    horizon_label: str = "",
) -> go.Figure:
    return build_sector_comparison_figure(snapshots)


build_comparison_dashboard_figure = build_comparison_figure


def open_comparison_chart(
    snapshots: list[dict],
    html_path: Path,
    *,
    horizon_label: str = "",
    open_browser: bool = True,
) -> tuple[Path, bool]:
    fig = build_comparison_figure(snapshots, horizon_label=horizon_label)
    html_path = Path(html_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    write_responsive_html(
        fig,
        html_path,
        banner_title=comparison_banner_title(snapshots, horizon_label=horizon_label),
        compare=True,
    )
    opened = open_html_file(html_path) if open_browser else False
    return html_path, opened


__all__ = [
    "build_comparison_figure",
    "build_comparison_dashboard_figure",
    "comparison_banner_title",
    "open_comparison_chart",
]
