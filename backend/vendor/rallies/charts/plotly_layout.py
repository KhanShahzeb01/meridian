"""Plotly layout constants and styling for valuation charts."""

from __future__ import annotations

import html as html_module
import re
from pathlib import Path

import plotly.graph_objects as go

FONT_FAMILY = "Arial"
FONT_AXIS_TITLE = dict(family="Arial Black", size=14, color="#111111")
FONT_AXIS_TICK = dict(family=FONT_FAMILY, size=14, color="#111111")
FONT_SUBPLOT_TITLE = dict(family="Arial Black", size=16, color="#111111")
FONT_LEGEND = dict(family="Arial Black", size=16, color="#111111")

# Grid spacing (paper coordinates)
H_GAP = 0.08  # between boxes in the same row
V_GAP = H_GAP * 2  # between rows (reduced; titles sit just above each panel)
TOP_GAP = H_GAP * 2  # space below HTML banner before first chart row
TITLE_PAD = 0.005  # panel title sits this far above the panel top edge
MARGIN_X = 0.06
MARGIN_Y_BOTTOM = 0.03
BANNER_BG = "#d4d4d4"
BANNER_TEXT = "#111111"
BANNER_HTML_HEIGHT_PX = 52
CHART_Y_TOP = 1.0

# Multi-ticker comparison (unchanged)
COMPARE_WIDTH = 1000
COMPARE_HEIGHT = 1100


def vertical_spacing_for_rows(nrows: int, cols: int = 1) -> float:
    if nrows <= 1:
        return 0.04
    cap = 1.0 / (nrows - 1) * 0.30
    return min(0.04, cap)


def _set_subplot_domain(
    fig: go.Figure,
    row: int,
    col: int,
    xdom: tuple[float, float],
    ydom: tuple[float, float],
) -> None:
    xy = fig.get_subplot(row, col)
    xy.xaxis.domain = xdom
    xy.yaxis.domain = ydom
    x_anchor = xy.xaxis.anchor
    for key in fig.layout:
        if not key.startswith("yaxis"):
            continue
        ya = fig.layout[key]
        if getattr(ya, "anchor", None) == x_anchor and getattr(ya, "overlaying", None):
            ya.domain = ydom


SECTOR_PANEL_TITLE_TEXT: dict[tuple[int, int], str] = {
    (1, 1): "EPS vs P/E (size ≈ price)",
    (1, 2): "Forward P/E vs trailing P/E",
    (2, 1): "Analyst target price ranges",
    (2, 2): "P/E vs EV/EBITDA (Burry zones)",
}

# Multi-ticker 2×2 — full width, large panels, clear column/row gaps
SECTOR_EDGE_X = 0.04
SECTOR_EDGE_Y = 0.035
SECTOR_H_GAP = 0.12
SECTOR_V_GAP = 0.09
SECTOR_TITLE_FRAC = 0.065
SECTOR_COLORBAR_FRAC = 0.09
SECTOR_COLORBAR_INSET = 0.45

SECTOR_COLORBAR_PANELS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Price ($)"),
    (2, 2, "PEG"),
)


def _sector_cell_box(row: int, col: int) -> tuple[float, float, float, float]:
    """Full box (xl, xr, yb, yt): spans viewport width; tall rows (page may scroll)."""
    inner_w = 1.0 - 2 * SECTOR_EDGE_X
    cell_w = (inner_w - SECTOR_H_GAP) / 2
    x0 = SECTOR_EDGE_X
    if col == 1:
        xl, xr = x0, x0 + cell_w
    else:
        xl, xr = x0 + cell_w + SECTOR_H_GAP, x0 + 2 * cell_w + SECTOR_H_GAP

    inner_h = 1.0 - 2 * SECTOR_EDGE_Y
    cell_h = (inner_h - SECTOR_V_GAP) / 2
    y0 = SECTOR_EDGE_Y
    if row == 1:
        yb, yt = y0 + cell_h + SECTOR_V_GAP, y0 + 2 * cell_h + SECTOR_V_GAP
    else:
        yb, yt = y0, y0 + cell_h
    return xl, xr, yb, yt


def _sector_plot_domain(row: int, col: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """Plot area inside the box: title band on top, colorbar strip on the right when needed."""
    xl, xr, yb, yt = _sector_cell_box(row, col)
    cw, ch = xr - xl, yt - yb
    y_plot = (yb, yt - SECTOR_TITLE_FRAC * ch)
    if (row, col) in {(1, 1), (2, 2)}:
        x_plot = (xl, xr - SECTOR_COLORBAR_FRAC * cw)
    else:
        x_plot = (xl, xr)
    return x_plot, y_plot


def apply_sector_compare_grid_domains(fig: go.Figure) -> None:
    """Equal square boxes in a centered 2×2 grid (figure container is square via HTML)."""
    for row in (1, 2):
        for col in (1, 2):
            try:
                xdom, ydom = _sector_plot_domain(row, col)
                _set_subplot_domain(fig, row, col, xdom, ydom)
            except Exception:
                continue


def position_sector_colorbars(fig: go.Figure) -> None:
    """Colorbar in the cell's right margin — clear of plot and neighboring column."""
    for row, col, ctitle in SECTOR_COLORBAR_PANELS:
        xl, xr, yb, yt = _sector_cell_box(row, col)
        x_plot, y_plot = _sector_plot_domain(row, col)
        strip_w = xr - x_plot[1]
        cb_x = x_plot[1] + strip_w * SECTOR_COLORBAR_INSET
        y_mid = (y_plot[0] + y_plot[1]) / 2
        plot_h = y_plot[1] - y_plot[0]
        fig.update_traces(
            marker=dict(
                colorbar=dict(
                    title=ctitle,
                    x=cb_x,
                    xref="paper",
                    y=y_mid,
                    yref="paper",
                    yanchor="middle",
                    len=plot_h * 0.8,
                    thickness=13,
                    outlinewidth=0,
                    xpad=4,
                )
            ),
            row=row,
            col=col,
            selector=dict(marker_showscale=True),
        )


def apply_sector_panel_titles(fig: go.Figure) -> None:
    """Title centered in the top band of each box."""
    for (row, col), text in SECTOR_PANEL_TITLE_TEXT.items():
        xl, xr, yb, yt = _sector_cell_box(row, col)
        ch = yt - yb
        x_mid = (xl + xr) / 2
        y_title = yt - SECTOR_TITLE_FRAC * ch * 0.35
        fig.add_annotation(
            text=f"<b>{text}</b>",
            xref="paper",
            yref="paper",
            x=x_mid,
            y=y_title,
            xanchor="center",
            yanchor="middle",
            showarrow=False,
            font=FONT_SUBPLOT_TITLE,
        )


def apply_sector_compare_layout(fig: go.Figure) -> None:
    """Wide compare figure; height set in HTML (vertical scroll allowed)."""
    fig.update_layout(
        autosize=True,
        margin=dict(l=0, r=0, t=0, b=0, pad=0),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family=FONT_FAMILY, size=14),
        hovermode="closest",
        showlegend=False,
    )
    style_axes(fig, nrows=2, ncols=2)


def apply_valuation_grid_domains(fig: go.Figure) -> None:
    """
    Explicit grid:
      row1: banner (full width)
      row2: fair | EPS          (horizontal gap H_GAP)
      row3: P/E | forward P/E | targets  (bottom-right two plots side by side)
    Vertical gap between rows is V_GAP; TOP_GAP clears space under the HTML banner.
    """
    usable_w = 1.0 - 2 * MARGIN_X
    box_w = (usable_w - H_GAP) / 2
    x_left = (MARGIN_X, MARGIN_X + box_w)
    x_right = (MARGIN_X + box_w + H_GAP, MARGIN_X + box_w + H_GAP + box_w)

    inner_w = (x_right[1] - x_right[0] - H_GAP) / 2
    x_fwd = (x_right[0], x_right[0] + inner_w)
    x_tgt = (x_right[0] + inner_w + H_GAP, x_right[1])

    chart_top = CHART_Y_TOP - TOP_GAP
    usable_h = chart_top - MARGIN_Y_BOTTOM
    box_h = (usable_h - V_GAP) / 2
    y_top = (MARGIN_Y_BOTTOM + box_h + V_GAP, chart_top)
    y_bottom = (MARGIN_Y_BOTTOM, MARGIN_Y_BOTTOM + box_h)

    panels = {
        (1, 1): (x_left, y_top),
        (1, 2): (x_right, y_top),
        (2, 1): (x_left, y_bottom),
        (2, 2): (x_fwd, y_bottom),
        (2, 3): (x_tgt, y_bottom),
    }
    for (row, col), (xdom, ydom) in panels.items():
        try:
            _set_subplot_domain(fig, row, col, xdom, ydom)
        except Exception:
            continue

    # Keep secondary y-axis for EPS panel aligned with row 1 col 2
    try:
        xy = fig.get_subplot(1, 2)
        x_anchor = xy.xaxis.anchor
        for key in fig.layout:
            if not key.startswith("yaxis"):
                continue
            ya = fig.layout[key]
            if getattr(ya, "anchor", None) == x_anchor and ya.domain is None:
                ya.domain = y_top
    except Exception:
        pass


def write_responsive_html(
    fig: go.Figure,
    html_path: Path,
    *,
    banner_title: str | None = None,
    compare: bool = False,
) -> None:
    """Write HTML: full-viewport chart + edge-to-edge light-gray banner header."""
    fig.update_layout(autosize=True)
    if getattr(fig.layout, "width", None) is not None:
        fig.update_layout(width=None)
    if getattr(fig.layout, "height", None) is not None:
        fig.update_layout(height=None)

    html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        config={
            "responsive": True,
            "displayModeBar": True,
            "scrollZoom": True,
        },
    )
    chart_h = f"calc(100vh - {BANNER_HTML_HEIGHT_PX}px)"
    if compare:
        chart_slot_css = """
body.rallies-compare-page {
  display: block;
  height: auto;
  min-height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}
.rallies-compare-slot {
  width: 100%;
  background: #ffffff;
  padding: 14px 18px 24px 18px;
  box-sizing: border-box;
}
.rallies-compare-slot .js-plotly-plot,
.rallies-compare-slot .plotly-graph-div {
  width: calc(100vw - 36px) !important;
  max-width: calc(100vw - 36px) !important;
  height: 88vw !important;
  min-height: 1020px !important;
  max-height: none !important;
}
"""
        plot_wrapper_rule = ""
        compare_body_override = """
html, body.rallies-compare-page {
  height: auto;
  overflow-x: hidden;
  overflow-y: auto;
}
body.rallies-compare-page {
  display: block;
}
"""
        body_bg = "#ffffff"
    else:
        compare_body_override = ""
        chart_slot_css = ""
        plot_wrapper_rule = f"""
.js-plotly-plot,
.plotly-graph-div,
body > div:not(.rallies-valuation-banner) {{
  width: 100vw !important;
  max-width: 100vw !important;
  height: {chart_h} !important;
  max-height: {chart_h} !important;
  flex: 1 1 auto;
  padding-top: 12px;
  box-sizing: border-box;
}}
"""
        body_bg = BANNER_BG

    viewport_css = f"""
<style>
html, body {{
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: {body_bg};
}}
body {{
  display: flex;
  flex-direction: column;
}}
.rallies-valuation-banner {{
  width: 100vw;
  max-width: 100%;
  box-sizing: border-box;
  background: {BANNER_BG};
  color: {BANNER_TEXT};
  font: bold 20px Arial, "Arial Black", sans-serif;
  text-align: center;
  padding: 14px 16px;
  margin: 0;
  border-bottom: 1px solid #b8b8b8;
  flex-shrink: 0;
}}
{compare_body_override}
{chart_slot_css}
{plot_wrapper_rule}
</style>
"""
    if "</head>" in html:
        html = html.replace("</head>", viewport_css + "</head>", 1)
    if compare:
        html = re.sub(r"<body>", '<body class="rallies-compare-page">', html, count=1)
    if banner_title and "<body" in html:
        safe = html_module.escape(banner_title)
        banner_html = f'<header class="rallies-valuation-banner">{safe}</header>'
        html = re.sub(r"(<body[^>]*>)", r"\1" + banner_html, html, count=1)
    if compare:
        html = re.sub(
            r'(<div id="[^"]*" class="plotly-graph-div"[^>]*>)',
            r'<div class="rallies-compare-slot">\1',
            html,
            count=1,
        )
        html = re.sub(
            r'(class="plotly-graph-div"[^>]*></div>)(\s*<script)',
            r"\1</div>\2",
            html,
            count=1,
        )
    Path(html_path).write_text(html, encoding="utf-8")


def subplot_axis_domain(fig: go.Figure, row: int, col: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """Read x/y paper domain for a subplot using Plotly's get_subplot()."""
    try:
        xy = fig.get_subplot(row, col)
        xdom = tuple(xy.xaxis.domain)
        ydom = tuple(xy.yaxis.domain)
        if ydom[0] is None or ydom[1] is None:
            raise ValueError("missing y domain")
        return xdom, ydom
    except Exception:
        return (0.0, 1.0), (0.0, 0.5)


PANEL_TITLE_TEXT: dict[tuple[int, int], str] = {
    (1, 1): "Fair value ($/sh) vs price ($/sh)",
    (1, 2): "Price ($/sh) vs trailing EPS ($/sh TTM)",
    (2, 1): "Trailing P/E (ratio; median & percentile band)",
    (2, 2): "Trailing vs forward P/E (ratio)",
    # (2, 3) uses apply_target_panel_titles — two lines (title + upside)
}


def apply_target_panel_titles(fig: go.Figure, market: dict) -> None:
    """Targets panel: title and upside on separate lines, centered above the chart."""
    row, col = 2, 3
    try:
        xdom, ydom = subplot_axis_domain(fig, row, col)
    except Exception:
        return
    x_mid = (xdom[0] + xdom[1]) / 2
    lines = ["Analyst targets vs price"]
    upside = market.get("target_upside_pct")
    if upside is not None:
        lines.append(f"Upside to mean: {upside:+.1f}%")
    text = "<br>".join(f"<b>{line}</b>" for line in lines)
    fig.add_annotation(
        text=text,
        xref="paper",
        yref="paper",
        x=x_mid,
        y=ydom[1] + TITLE_PAD,
        xanchor="center",
        yanchor="bottom",
        showarrow=False,
        font=FONT_SUBPLOT_TITLE,
    )


def apply_panel_titles(fig: go.Figure) -> None:
    """Centered titles immediately above each panel (paper coords)."""
    for (row, col), text in PANEL_TITLE_TEXT.items():
        try:
            xdom, ydom = subplot_axis_domain(fig, row, col)
        except Exception:
            continue
        x_mid = (xdom[0] + xdom[1]) / 2
        fig.add_annotation(
            text=f"<b>{text}</b>",
            xref="paper",
            yref="paper",
            x=x_mid,
            y=ydom[1] + TITLE_PAD,
            xanchor="center",
            yanchor="bottom",
            showarrow=False,
            font=FONT_SUBPLOT_TITLE,
        )


def place_legend_below_panel(
    fig: go.Figure,
    legend_key: str,
    x_domain: tuple[float, float],
    y_domain: tuple[float, float],
) -> None:
    """Position a named legend just under a subplot's domain."""
    x_mid = (x_domain[0] + x_domain[1]) / 2
    y_below = max(0.01, y_domain[0] - 0.03)
    leg_layout = dict(
        orientation="h",
        yanchor="top",
        y=y_below,
        x=x_mid,
        xanchor="center",
        bgcolor="rgba(255,255,255,0.95)",
        bordercolor="#dee2e6",
        borderwidth=1,
        font=FONT_LEGEND,
        tracegroupgap=6,
    )
    if legend_key == "legend":
        fig.update_layout(legend=leg_layout)
    else:
        fig.update_layout({legend_key: leg_layout})


def style_axes(fig: go.Figure, *, nrows: int = 4, ncols: int = 2) -> None:
    """Apply Arial 14 axis labels."""
    for r in range(1, nrows + 1):
        for c in range(1, ncols + 1):
            try:
                fig.update_xaxes(
                    row=r,
                    col=c,
                    title_font=FONT_AXIS_TITLE,
                    tickfont=FONT_AXIS_TICK,
                    showgrid=True,
                    gridwidth=1,
                    gridcolor="rgba(0,0,0,0.06)",
                    showline=True,
                    linewidth=1,
                    linecolor="#ccc",
                    automargin=True,
                )
                fig.update_yaxes(
                    row=r,
                    col=c,
                    title_font=FONT_AXIS_TITLE,
                    tickfont=FONT_AXIS_TICK,
                    showgrid=True,
                    gridwidth=1,
                    gridcolor="rgba(0,0,0,0.06)",
                    showline=True,
                    linewidth=1,
                    linecolor="#ccc",
                    automargin=True,
                )
            except Exception:
                pass


def apply_valuation_grid_layout(fig: go.Figure) -> None:
    """2×2 valuation grid; banner is rendered in HTML (full viewport width)."""
    fig.update_layout(
        autosize=True,
        margin=dict(l=0, r=0, t=4, b=28, pad=0),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family=FONT_FAMILY, size=14),
        hovermode="x unified",
        showlegend=False,
    )
    style_axes(fig, nrows=2, ncols=3)


def apply_compare_layout(fig: go.Figure, *, title: str) -> None:
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=14, family=FONT_FAMILY)),
        autosize=False,
        width=COMPARE_WIDTH,
        height=COMPARE_HEIGHT,
        margin=dict(l=52, r=40, t=56, b=48),
        paper_bgcolor="#f0f2f5",
        plot_bgcolor="#ffffff",
        font=dict(size=14, family=FONT_FAMILY),
        showlegend=False,
    )
    fig.update_annotations(font=FONT_SUBPLOT_TITLE, yshift=8)
    for r in (1, 2):
        for c in (1, 2):
            fig.update_xaxes(
                row=r,
                col=c,
                title_font=FONT_AXIS_TITLE,
                tickfont=FONT_AXIS_TICK,
                showgrid=True,
                gridcolor="rgba(0,0,0,0.06)",
                showline=True,
                linecolor="#ccc",
            )
            fig.update_yaxes(
                row=r,
                col=c,
                title_font=FONT_AXIS_TITLE,
                tickfont=FONT_AXIS_TICK,
                showgrid=True,
                gridcolor="rgba(0,0,0,0.06)",
                showline=True,
                linecolor="#ccc",
            )


def apply_dashboard_layout(
    fig: go.Figure,
    *,
    title: str,
    nrows: int,
    ncols: int = 1,
    height_per_row: int = 300,
    show_legend: bool = True,
) -> None:
    if ncols == 2 and nrows == 2:
        apply_compare_layout(fig, title=title)
        return
    apply_valuation_grid_layout(fig, banner_title=title)
