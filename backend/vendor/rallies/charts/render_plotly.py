"""Plotly chart renderer (PNG via Kaleido)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .data import MetricSeries

WIDTH = 1400
HEIGHT = 600
SCALE = 2  # effective higher res


def render_chart(
    series: MetricSeries,
    metric: str,
    out_path: Path,
    *,
    show_terminal: bool = False,
    console=None,
) -> Path:
    import plotly.graph_objects as go

    df = series.frame
    col = "peg" if metric == "peg" else "pe"
    plot_df = df.dropna(subset=[col]).copy()
    if plot_df.empty:
        raise ValueError(f"No {col.upper()} data to plot")

    y = plot_df[col]
    x = plot_df.index
    median = float(y.median())
    p25 = float(y.quantile(0.25))
    p75 = float(y.quantile(0.75))

    title_metric = "P/E" if metric == "pe" else "PEG"
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=[p75] * len(x),
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=[p25] * len(x),
            fill="tonexty",
            fillcolor="rgba(168, 218, 220, 0.35)",
            mode="lines",
            line=dict(width=0),
            name="25th–75th %ile",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            name=title_metric,
            line=dict(color="#2E86AB", width=3),
        )
    )
    fig.add_hline(
        y=median,
        line_dash="dash",
        line_color="#E94F37",
        annotation_text=f"Median {median:.1f}",
        annotation_position="right",
    )
    if metric == "peg":
        fig.add_hline(y=1, line_dash="dot", line_color="#6C757D", annotation_text="PEG=1")
        fig.add_hline(y=2, line_dash="dot", line_color="#9AA0A6", annotation_text="PEG=2")

    fig.update_layout(
        title=dict(
            text=(
                f"{series.company_name} ({series.ticker}) — "
                f"Trailing {title_metric} — {series.horizon.label}"
            ),
            font=dict(size=20),
        ),
        template="plotly_white",
        width=WIDTH,
        height=HEIGHT,
        font=dict(family="Inter, Helvetica, Arial, sans-serif", size=14),
        xaxis_title="Date",
        yaxis_title=title_metric,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=60, r=40, t=80, b=50),
        hovermode="x unified",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig.write_image(str(out_path), scale=SCALE)
    except Exception as e:
        raise RuntimeError(
            "Plotly static export failed. Install kaleido: pip install kaleido"
        ) from e
    if show_terminal and console is not None:
        from .display import display_chart_in_terminal

        if not display_chart_in_terminal(out_path, console):
            console.print(
                "[dim]Tip: install [cyan]chafa[/cyan] for inline charts, or use [cyan]--save[/cyan] "
                f"to write PNGs under .rallies/charts/[/dim]"
            )
    return out_path
