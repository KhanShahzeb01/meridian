"""
Plotly charts ported from stocks_valuation/utils.py (sector comparison notebook).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .plotly_layout import (
    apply_sector_compare_grid_domains,
    apply_sector_compare_layout,
    apply_sector_panel_titles,
    position_sector_colorbars,
)


def snapshots_to_frame(snapshots: list[dict]) -> pd.DataFrame:
    """Normalize comparison snapshots to notebook-style column names."""
    rows = []
    for s in snapshots:
        rows.append(
            {
                "Ticker": s["ticker"],
                "EPS": s.get("eps"),
                "P/E Ratio": s.get("pe"),
                "Forward P/E": s.get("forward_pe"),
                "Forward EPS": s.get("forward_eps"),
                "Price": s.get("price"),
                "PEG Ratio": s.get("peg"),
                "EV to EBITDA": s.get("ev_to_ebitda"),
                "Target Mean Price": s.get("target_mean"),
                "Target High Price": s.get("target_high"),
                "Target Low Price": s.get("target_low"),
            }
        )
    return pd.DataFrame(rows)


def build_sector_comparison_figure(snapshots: list[dict]) -> go.Figure:
    """Four-panel 2×2 sector comparison (scatter/range charts from notebook)."""
    df = snapshots_to_frame(snapshots)
    if df.empty:
        raise ValueError("No snapshots to compare")

    fig = make_subplots(rows=2, cols=2)

    _panel_eps_pe_quadrant(fig, df, row=1, col=1)
    _panel_trailing_forward_pe(fig, df, row=1, col=2)
    _panel_target_ranges(fig, df, row=2, col=1)
    _panel_pe_ev_ebitda(fig, df, row=2, col=2)

    apply_sector_compare_layout(fig)
    apply_sector_compare_grid_domains(fig)
    position_sector_colorbars(fig)
    apply_sector_panel_titles(fig)
    return fig


def _panel_eps_pe_quadrant(fig: go.Figure, df: pd.DataFrame, row: int, col: int) -> None:
    plot_df = df.dropna(subset=["EPS", "P/E Ratio"])
    if plot_df.empty:
        return

    x_min = float(plot_df["EPS"].min()) * 0.85
    x_max = float(plot_df["EPS"].max()) * 1.15
    y_min = float(plot_df["P/E Ratio"].min()) * 0.85
    y_max = float(plot_df["P/E Ratio"].max()) * 1.15

    sizes = (plot_df["Price"].fillna(1) / 5).tolist()
    fig.add_trace(
        go.Scatter(
            x=plot_df["EPS"],
            y=plot_df["P/E Ratio"],
            mode="markers+text",
            text=plot_df["Ticker"],
            textposition="top center",
            marker=dict(
                size=sizes,
                color=plot_df["Price"],
                colorscale="Viridis",
                showscale=col == 1 and row == 1,
            ),
            hovertemplate=(
                "<b>%{text}</b><br>EPS $%{x:.2f}<br>P/E %{y:.1f}<extra></extra>"
            ),
        ),
        row=row,
        col=col,
    )
    fig.update_xaxes(title_text="EPS ($)", range=[x_min, x_max], row=row, col=col)
    fig.update_yaxes(title_text="P/E", range=[y_min, y_max], row=row, col=col)


def _panel_trailing_forward_pe(fig: go.Figure, df: pd.DataFrame, row: int, col: int) -> None:
    plot_df = df.dropna(subset=["P/E Ratio", "Forward P/E"])
    if plot_df.empty:
        return

    fig.add_trace(
        go.Scatter(
            x=plot_df["P/E Ratio"],
            y=plot_df["Forward P/E"],
            mode="markers+text",
            text=plot_df["Ticker"],
            textposition="top center",
            marker=dict(
                size=(plot_df["Price"].fillna(50) / 5).tolist(),
                color=plot_df["EPS"],
                colorscale="Viridis",
                showscale=False,
            ),
            hovertemplate=(
                "<b>%{text}</b><br>Trailing P/E %{x:.1f}<br>"
                "Forward P/E %{y:.1f}<extra></extra>"
            ),
        ),
        row=row,
        col=col,
    )
    max_pe = max(float(plot_df["P/E Ratio"].max()), float(plot_df["Forward P/E"].max())) + 5
    fig.add_trace(
        go.Scatter(
            x=[0, max_pe],
            y=[0, max_pe],
            mode="lines",
            line=dict(color="red", dash="dash"),
            name="Forward = Trailing",
            hoverinfo="skip",
        ),
        row=row,
        col=col,
    )
    fig.update_xaxes(title_text="Trailing P/E", range=[0, max_pe], row=row, col=col)
    fig.update_yaxes(title_text="Forward P/E", range=[0, max_pe], row=row, col=col)


def _panel_target_ranges(fig: go.Figure, df: pd.DataFrame, row: int, col: int) -> None:
    req = ["Target Low Price", "Target High Price", "Target Mean Price", "Price"]
    plot_df = df.dropna(subset=[c for c in req if c in df.columns])
    if plot_df.empty or len(plot_df) < 1:
        return

    for _, row_s in plot_df.iterrows():
        ticker = row_s["Ticker"]
        lo = row_s.get("Target Low Price")
        hi = row_s.get("Target High Price")
        if pd.notna(lo) and pd.notna(hi):
            fig.add_trace(
                go.Scatter(
                    x=[ticker, ticker],
                    y=[lo, hi],
                    mode="lines",
                    line=dict(width=12, color="lightblue"),
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=row,
                col=col,
            )

    if plot_df["Target Mean Price"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=plot_df["Ticker"],
                y=plot_df["Target Mean Price"],
                mode="markers",
                marker=dict(size=10, color="blue"),
                name="Target mean",
                hovertemplate="%{x}<br>Target mean $%{y:.2f}<extra></extra>",
            ),
            row=row,
            col=col,
        )
    if plot_df["Price"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=plot_df["Ticker"],
                y=plot_df["Price"],
                mode="markers",
                marker=dict(size=12, color="black", symbol="x"),
                name="Current price",
                hovertemplate="%{x}<br>Price $%{y:.2f}<extra></extra>",
            ),
            row=row,
            col=col,
        )
    fig.update_yaxes(title_text="Price ($)", row=row, col=col)


def _panel_pe_ev_ebitda(fig: go.Figure, df: pd.DataFrame, row: int, col: int) -> None:
    plot_df = df.dropna(subset=["P/E Ratio", "EV to EBITDA", "PEG Ratio"])
    plot_df = plot_df[
        (plot_df["P/E Ratio"] > 0)
        & (plot_df["EV to EBITDA"] > 0)
        & (plot_df["PEG Ratio"] > 0)
    ]
    if plot_df.empty:
        fig.add_annotation(
            text="EV/EBITDA not available for these tickers",
            xref="x domain",
            yref="y domain",
            x=0.5,
            y=0.5,
            showarrow=False,
            row=row,
            col=col,
        )
        return

    fig.add_trace(
        go.Scatter(
            x=plot_df["P/E Ratio"],
            y=plot_df["EV to EBITDA"],
            mode="markers+text",
            text=plot_df["Ticker"],
            textposition="top center",
            marker=dict(
                size=np.abs(plot_df["EPS"].fillna(1)) * 2,
                color=plot_df["PEG Ratio"],
                colorscale="RdYlGn_r",
                showscale=True,
            ),
            hovertemplate=(
                "<b>%{text}</b><br>P/E %{x:.1f}<br>EV/EBITDA %{y:.1f}<extra></extra>"
            ),
        ),
        row=row,
        col=col,
    )
    max_pe = float(plot_df["P/E Ratio"].max()) * 1.15
    max_ev = float(plot_df["EV to EBITDA"].max()) * 1.15
    fig.add_shape(
        type="rect", x0=0, y0=0, x1=15, y1=10,
        fillcolor="rgba(0,255,0,0.15)", line_width=0, row=row, col=col,
    )
    fig.add_vline(x=15, line_dash="dash", line_color="green", row=row, col=col)
    fig.add_hline(y=10, line_dash="dash", line_color="green", row=row, col=col)
    fig.update_xaxes(title_text="P/E", range=[0, max_pe], row=row, col=col)
    fig.update_yaxes(title_text="EV/EBITDA", range=[0, max_ev], row=row, col=col)
