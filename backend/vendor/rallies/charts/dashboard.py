"""
Valuation dashboard: Price+EPS, P/E band, PEG (trailing metrics only).

Charting rules: time on X for series; explicit axis labels; line charts for
time series; scatter for P/E vs growth; dual Y only on panel A with labels.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .data import MetricSeries

FIG_W = 14
FIG_H_PER_PANEL = 4.2
DPI = 160

PALETTE = {
    "price": "#1B4965",
    "eps": "#E76F51",
    "pe_line": "#2E86AB",
    "peg_line": "#6A4C93",
    "median": "#E94F37",
    "band": "#A8DADC",
    "peg_ref": "#6C757D",
    "scatter": "#2A9D8F",
}


def _date_range_label(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    return f"{df.index.min().date()} → {df.index.max().date()}"


def _trailing_subtitle(series: MetricSeries) -> str:
    dr = _date_range_label(series.frame)
    return (
        f"{series.company_name} ({series.ticker}) — Trailing metrics — "
        f"{series.horizon.label} — {dr}"
    )


def render_valuation_dashboard(
    series: MetricSeries,
    out_path: Path,
    *,
    include_scatter: bool = False,
    show_terminal: bool = False,
    console=None,
) -> Path:
    """3-panel (or 4-panel with --scatter) trailing valuation dashboard."""
    df = series.frame.copy()
    if df.empty:
        raise ValueError("No data to plot for this horizon.")

    nrows = 4 if include_scatter else 3
    fig_h = FIG_H_PER_PANEL * nrows + 1.5
    fig, axes = plt.subplots(nrows, 1, figsize=(FIG_W, fig_h), dpi=DPI)
    if nrows == 1:
        axes = [axes]

    sns.set_theme(
        style="whitegrid",
        context="talk",
        font_scale=0.95,
        rc={
            "axes.facecolor": "#FAFAFA",
            "figure.facecolor": "#FFFFFF",
            "grid.alpha": 0.35,
        },
    )

    subtitle = _trailing_subtitle(series)
    fig.suptitle(subtitle, fontsize=14, fontweight="bold", y=0.995)

    _panel_price_eps(axes[0], df)
    _panel_pe_history(axes[1], df)
    _panel_peg_history(axes[2], df)
    if include_scatter:
        _panel_pe_vs_growth(axes[3], df, series.ticker)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    if show_terminal and console is not None:
        from .display import display_chart_in_terminal

        if not display_chart_in_terminal(out_path, console):
            console.print(
                "[dim]Install [cyan]chafa[/cyan] for inline preview, or use [cyan]--save[/cyan].[/dim]"
            )
    return out_path


def _panel_price_eps(ax, df: pd.DataFrame) -> None:
    """A. Price and trailing EPS over time (dual axis, labeled)."""
    x = df.index
    ax.plot(x, df["price"], color=PALETTE["price"], linewidth=2.2, label="Price")
    ax.set_ylabel("Price ($)")
    ax.set_xlabel("Date")

    ax2 = ax.twinx()
    ax2.plot(
        x,
        df["eps_ttm"],
        color=PALETTE["eps"],
        linewidth=2.0,
        linestyle="--",
        label="EPS (trailing)",
    )
    ax2.set_ylabel("EPS (trailing $)")

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left", frameon=True)
    ax.set_title("A. Price vs trailing EPS", fontweight="bold", loc="left")
    sns.despine(ax=ax, right=False)


def _panel_pe_history(ax, df: pd.DataFrame) -> None:
    """B. Trailing P/E over time with 25th–75th percentile band and median."""
    plot_df = df.dropna(subset=["pe"])
    if plot_df.empty:
        ax.text(0.5, 0.5, "No P/E data", ha="center", va="center", transform=ax.transAxes)
        return

    x = plot_df.index
    y = plot_df["pe"]
    p25 = float(y.quantile(0.25))
    p75 = float(y.quantile(0.75))
    median = float(y.median())

    ax.fill_between(x, p25, p75, color=PALETTE["band"], alpha=0.4, label="25th–75th %ile")
    ax.axhline(median, color=PALETTE["median"], linestyle="--", linewidth=1.5, label=f"Median {median:.1f}")
    ax.plot(x, y, color=PALETTE["pe_line"], linewidth=2.2, label="P/E")

    ax.set_xlabel("Date")
    ax.set_ylabel("P/E")
    ax.set_title("B. Trailing P/E vs history", fontweight="bold", loc="left")
    ax.legend(loc="upper left", frameon=True)
    sns.despine(ax=ax)


def _panel_peg_history(ax, df: pd.DataFrame) -> None:
    """C. Trailing PEG over time with reference at PEG = 1."""
    plot_df = df.dropna(subset=["peg"])
    if plot_df.empty:
        ax.text(
            0.5,
            0.5,
            "PEG not available\n(non-positive or missing EPS growth)",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_xlabel("Date")
        ax.set_ylabel("PEG")
        ax.set_title("D. PEG YoY (not Yahoo 5yr PEG)", fontweight="bold", loc="left")
        return

    x = plot_df.index
    y = plot_df["peg"]
    ax.axhline(1.0, color=PALETTE["peg_ref"], linestyle=":", linewidth=1.5, label="PEG = 1")
    ax.plot(x, y, color=PALETTE["peg_line"], linewidth=2.2, label="PEG YoY")
    ax.set_xlabel("Date")
    ax.set_ylabel("PEG YoY")
    ax.set_title("D. PEG YoY (not Yahoo 5yr PEG)", fontweight="bold", loc="left")
    ax.legend(loc="upper left", frameon=True)
    sns.despine(ax=ax)


def _panel_pe_vs_growth(ax, df: pd.DataFrame, ticker: str) -> None:
    """D. Scatter: EPS growth % vs P/E (trailing, same window)."""
    plot_df = df.dropna(subset=["pe", "eps_growth_yoy"]).copy()
    plot_df = plot_df[plot_df["eps_growth_yoy"] > 0]
    if len(plot_df) < 3:
        ax.text(0.5, 0.5, "Insufficient growth points", ha="center", va="center", transform=ax.transAxes)
        ax.set_xlabel("EPS Growth %")
        ax.set_ylabel("P/E")
        ax.set_title("D. P/E vs EPS growth (trailing)", fontweight="bold", loc="left")
        return

    sizes = (plot_df["price"] / plot_df["price"].max() * 80 + 15).values
    ax.scatter(
        plot_df["eps_growth_yoy"],
        plot_df["pe"],
        s=sizes,
        alpha=0.55,
        color=PALETTE["scatter"],
        edgecolors="white",
        linewidths=0.5,
    )
    # Highlight latest point
    last = plot_df.iloc[-1]
    ax.scatter(
        [last["eps_growth_yoy"]],
        [last["pe"]],
        s=120,
        color=PALETTE["median"],
        edgecolors="black",
        linewidths=1,
        zorder=5,
        label="Latest",
    )
    ax.set_xlabel("EPS Growth %")
    ax.set_ylabel("P/E")
    ax.set_title("D. P/E vs EPS growth (trailing)", fontweight="bold", loc="left")
    ax.legend(loc="upper left", frameon=True)
    sns.despine(ax=ax)
