"""Seaborn/matplotlib chart renderer."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .data import MetricSeries

# Wide rectangle, high DPI
FIG_W = 14
FIG_H = 6
DPI = 300

PALETTE = {
    "line": "#2E86AB",
    "median": "#E94F37",
    "band": "#A8DADC",
    "peg_ref": "#6C757D",
}


def render_chart(
    series: MetricSeries,
    metric: str,
    out_path: Path,
    *,
    show_terminal: bool = False,
    console=None,
) -> Path:
    df = series.frame
    col = "peg" if metric == "peg" else "pe"
    plot_df = df.dropna(subset=[col]).copy()
    if plot_df.empty:
        raise ValueError(f"No {col.upper()} data to plot")

    sns.set_theme(
        style="whitegrid",
        context="talk",
        font_scale=1.05,
        rc={
            "figure.figsize": (FIG_W, FIG_H),
            "axes.titlesize": 16,
            "axes.labelsize": 13,
            "legend.fontsize": 11,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "axes.facecolor": "#FAFAFA",
            "figure.facecolor": "#FFFFFF",
            "grid.alpha": 0.35,
        },
    )

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=DPI)
    y = plot_df[col]
    x = plot_df.index

    median = float(y.median())
    p25 = float(y.quantile(0.25))
    p75 = float(y.quantile(0.75))

    ax.fill_between(x, p25, p75, color=PALETTE["band"], alpha=0.35, label="25th–75th %ile")
    ax.axhline(median, color=PALETTE["median"], linestyle="--", linewidth=1.5, label=f"Median {median:.1f}")
    if metric == "peg":
        ax.axhline(1.0, color=PALETTE["peg_ref"], linestyle=":", linewidth=1.2, label="PEG = 1")
        ax.axhline(2.0, color=PALETTE["peg_ref"], linestyle=":", linewidth=1.0, alpha=0.7, label="PEG = 2")

    sns.lineplot(
        x=x,
        y=y,
        ax=ax,
        color=PALETTE["line"],
        linewidth=2.4,
        label=col.upper(),
    )

    title_metric = "P/E" if metric == "pe" else "PEG"
    ax.set_title(
        f"{series.company_name} ({series.ticker}) — Trailing {title_metric} — {series.horizon.label}",
        fontweight="bold",
        pad=12,
    )
    ax.set_xlabel("Date")
    ax.set_ylabel(title_metric)
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#CCCCCC")
    sns.despine(ax=ax)
    fig.autofmt_xdate(rotation=25)
    fig.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    if show_terminal and console is not None:
        from .display import display_chart_in_terminal

        if not display_chart_in_terminal(out_path, console):
            console.print(
                "[dim]Tip: install [cyan]chafa[/cyan] for inline charts, or use [cyan]--save[/cyan] "
                f"to write PNGs under .rallies/charts/[/dim]"
            )
    return out_path
