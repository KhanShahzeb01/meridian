"""Plotly valuation dashboard — 2×2 grid + banner, opens in browser."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .browser import open_html_file
from .data import MetricSeries
from .plotly_layout import (
    TOP_GAP,
    apply_panel_titles,
    apply_target_panel_titles,
    apply_valuation_grid_domains,
    apply_valuation_grid_layout,
    place_legend_below_panel,
    style_axes,
    subplot_axis_domain,
    write_responsive_html,
)

COLORS = {
    "price": "#1B4965",
    "eps": "#E76F51",
    "pe": "#2E86AB",
    "median": "#E94F37",
    "band": "rgba(168, 218, 220, 0.45)",
    "lynch_band": "rgba(42, 157, 143, 0.25)",
    "lynch_fair": "#2A9D8F",
    "forward": "#2A9D8F",
    "target_band": "lightblue",
    "target_mean": "#2563eb",
    "current": "#111111",
}

PANEL_LEGENDS = ("legend", "legend2", "legend3", "legend4", "legend5")


def _banner_title(series: MetricSeries) -> str:
    return f"{series.ticker} Valuation Charts"


def _add_lynch_panel(fig: go.Figure, df: pd.DataFrame, row: int, col: int, leg: str) -> None:
    x = df.index
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["price"],
            name="Price",
            legend=leg,
            line=dict(color=COLORS["price"], width=2.5),
            hovertemplate="%{x|%Y-%m-%d}<br>Price $%{y:.2f}<extra></extra>",
        ),
        row=row,
        col=col,
    )
    if "price_fair_high" not in df.columns:
        fig.update_yaxes(title_text="Price ($)", row=row, col=col)
        fig.update_xaxes(title_text="Date", row=row, col=col)
        return
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["price_fair_high"],
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ),
        row=row,
        col=col,
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["price_fair_low"],
            fill="tonexty",
            fillcolor=COLORS["lynch_band"],
            line=dict(width=0),
            name="Fair range (P/E 25th–75th × EPS)",
            legend=leg,
            hoverinfo="skip",
        ),
        row=row,
        col=col,
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["price_fair_median"],
            name="Fair value (median P/E × EPS)",
            legend=leg,
            line=dict(color=COLORS["lynch_fair"], width=1.5, dash="dash"),
            hovertemplate="%{x|%Y-%m-%d}<br>Fair $%{y:.2f}<extra></extra>",
        ),
        row=row,
        col=col,
    )
    fig.update_yaxes(title_text="Price ($)", row=row, col=col)
    fig.update_xaxes(title_text="Date", row=row, col=col)


def _add_price_eps_panel(fig: go.Figure, df: pd.DataFrame, row: int, col: int, leg: str) -> None:
    x = df.index
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["price"],
            name="Price",
            legend=leg,
            line=dict(color=COLORS["price"], width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>Price $%{y:.2f}<extra></extra>",
        ),
        row=row,
        col=col,
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["eps_ttm"],
            name="EPS (trailing)",
            legend=leg,
            line=dict(color=COLORS["eps"], width=2, dash="dash"),
            hovertemplate="%{x|%Y-%m-%d}<br>EPS $%{y:.2f}<extra></extra>",
        ),
        row=row,
        col=col,
        secondary_y=True,
    )
    fig.update_yaxes(title_text="Price ($)", row=row, col=col, secondary_y=False)
    fig.update_yaxes(title_text="EPS (trailing $)", row=row, col=col, secondary_y=True)
    fig.update_xaxes(title_text="Date", row=row, col=col)


def _add_pe_panel(fig: go.Figure, df: pd.DataFrame, row: int, col: int, leg: str) -> None:
    pe_df = df.dropna(subset=["pe"])
    if pe_df.empty:
        fig.update_yaxes(title_text="P/E", row=row, col=col)
        fig.update_xaxes(title_text="Date", row=row, col=col)
        return
    y = pe_df["pe"]
    p25, p75, med = float(y.quantile(0.25)), float(y.quantile(0.75)), float(y.median())
    fig.add_trace(
        go.Scatter(
            x=pe_df.index,
            y=[p75] * len(pe_df),
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ),
        row=row,
        col=col,
    )
    fig.add_trace(
        go.Scatter(
            x=pe_df.index,
            y=[p25] * len(pe_df),
            fill="tonexty",
            fillcolor=COLORS["band"],
            line=dict(width=0),
            name="25th–75th %ile band",
            legend=leg,
            hoverinfo="skip",
        ),
        row=row,
        col=col,
    )
    fig.add_trace(
        go.Scatter(
            x=pe_df.index,
            y=y,
            name="Trailing P/E",
            legend=leg,
            line=dict(color=COLORS["pe"], width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>P/E %{y:.2f}<extra></extra>",
        ),
        row=row,
        col=col,
    )
    fig.add_hline(
        y=med,
        line_dash="dash",
        line_color=COLORS["median"],
        annotation_text=f"Median {med:.1f}",
        annotation_font_size=12,
        row=row,
        col=col,
    )
    fig.update_yaxes(title_text="P/E", row=row, col=col)
    fig.update_xaxes(title_text="Date", row=row, col=col)


def _add_trailing_forward_pe_panel(
    fig: go.Figure, market: dict, trailing_pe: float, row: int, col: int, leg: str
) -> None:
    fpe = market.get("forward_pe")
    if fpe is None:
        fig.add_annotation(
            text="Forward P/E not available",
            xref="x domain",
            yref="y domain",
            x=0.5,
            y=0.5,
            showarrow=False,
            row=row,
            col=col,
        )
        fig.update_yaxes(title_text="P/E", row=row, col=col)
        return

    fig.add_trace(
        go.Bar(
            x=["Trailing P/E", "Forward P/E"],
            y=[trailing_pe, fpe],
            marker_color=[COLORS["pe"], COLORS["forward"]],
            text=[f"{trailing_pe:.1f}", f"{fpe:.1f}"],
            textposition="outside",
            showlegend=False,
            hovertemplate="%{x}<br>%{y:.1f}<extra></extra>",
        ),
        row=row,
        col=col,
    )
    fig.update_yaxes(title_text="P/E", row=row, col=col)


def _add_target_price_panel(
    fig: go.Figure, market: dict, row: int, col: int, leg: str
) -> None:
    price = market.get("price")
    lo = market.get("target_low")
    hi = market.get("target_high")
    mean = market.get("target_mean")
    if price is None or mean is None:
        fig.add_annotation(
            text="Analyst targets not available",
            xref="x domain",
            yref="y domain",
            x=0.5,
            y=0.5,
            showarrow=False,
            row=row,
            col=col,
        )
        fig.update_yaxes(title_text="Price ($)", row=row, col=col)
        return

    lbl = "Current"
    if lo is not None and hi is not None:
        fig.add_trace(
            go.Scatter(
                x=[lbl, lbl],
                y=[lo, hi],
                mode="lines",
                line=dict(width=16, color=COLORS["target_band"]),
                name="Target range",
                legend=leg,
                hoverinfo="skip",
            ),
            row=row,
            col=col,
        )
    fig.add_trace(
        go.Scatter(
            x=[lbl],
            y=[mean],
            mode="markers",
            marker=dict(size=12, color=COLORS["target_mean"]),
            name="Target mean",
            legend=leg,
            hovertemplate="Target mean $%{y:.2f}<extra></extra>",
        ),
        row=row,
        col=col,
    )
    fig.add_trace(
        go.Scatter(
            x=[lbl],
            y=[price],
            mode="markers",
            marker=dict(size=14, color=COLORS["current"], symbol="x"),
            name="Current price",
            legend=leg,
            hovertemplate="Current $%{y:.2f}<extra></extra>",
        ),
        row=row,
        col=col,
    )
    fig.update_yaxes(title_text="Price ($)", row=row, col=col)


def _position_panel_legends(fig: go.Figure) -> None:
    panels = [
        (1, 1, PANEL_LEGENDS[0]),
        (1, 2, PANEL_LEGENDS[1]),
        (2, 1, PANEL_LEGENDS[2]),
        (2, 2, PANEL_LEGENDS[3]),
        (2, 3, PANEL_LEGENDS[4]),
    ]
    for row, col, leg in panels:
        xdom, ydom = subplot_axis_domain(fig, row, col)
        place_legend_below_panel(fig, leg, xdom, ydom)


def build_valuation_dashboard_figure(series: MetricSeries) -> go.Figure:
    df = series.frame.copy()
    if df.empty:
        raise ValueError("No data to plot.")

    market = series.market or {}
    pe_now = float(df["pe"].dropna().iloc[-1]) if df["pe"].notna().any() else 0.0

    fig = make_subplots(
        rows=2,
        cols=3,
        specs=[
            [{}, {"secondary_y": True}, None],
            [{}, {}, {}],
        ],
        horizontal_spacing=0.08,
        vertical_spacing=0.06,
    )

    _add_lynch_panel(fig, df, 1, 1, PANEL_LEGENDS[0])
    _add_price_eps_panel(fig, df, 1, 2, PANEL_LEGENDS[1])
    _add_pe_panel(fig, df, 2, 1, PANEL_LEGENDS[2])
    _add_trailing_forward_pe_panel(fig, market, pe_now, 2, 2, PANEL_LEGENDS[3])
    _add_target_price_panel(fig, market, 2, 3, PANEL_LEGENDS[4])

    apply_valuation_grid_layout(fig)
    style_axes(fig, nrows=2, ncols=3)
    apply_valuation_grid_domains(fig)
    apply_panel_titles(fig)
    apply_target_panel_titles(fig, market)
    _position_panel_legends(fig)

    if not df.empty:
        dr = f"{df.index.min().date()} → {df.index.max().date()}"
        fig.add_annotation(
            text=f"{series.company_name} · {series.horizon.label} · {dr}",
            xref="paper",
            yref="paper",
            x=0.5,
            y=1.0 - TOP_GAP + 0.01,
            yanchor="bottom",
            xanchor="center",
            showarrow=False,
            font=dict(size=11, color="#555"),
        )

    return fig


def open_valuation_dashboard(
    series: MetricSeries,
    html_path: Path,
    *,
    open_browser: bool = True,
) -> tuple[Path, bool]:
    fig = build_valuation_dashboard_figure(series)
    html_path = Path(html_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    write_responsive_html(fig, html_path, banner_title=_banner_title(series))
    opened = open_html_file(html_path) if open_browser else False
    return html_path, opened
