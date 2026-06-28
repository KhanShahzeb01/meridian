"""E. Multi-ticker valuation comparison (bar chart, trailing snapshot)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .data import MetricSeries, build_pe_frame, peg_for_display, slice_for_horizon
from .horizons import horizon_for_key
from .snapshot import fetch_market_snapshot

FIG_W = 12
FIG_H = 6
DPI = 160


def snapshot_from_series(series: MetricSeries) -> dict:
    df = series.frame
    if df.empty:
        return {}
    row = df.iloc[-1]
    peg_yoy, _ = peg_for_display(row)
    market = series.market or fetch_market_snapshot(series.ticker)
    peg_5yr = market.get("peg_trailing") if market else None
    pe_trailing = float(row.get("pe", float("nan")))
    if market and market.get("pe_trailing") is not None:
        pe_trailing = float(market["pe_trailing"])
    snap = {
        "ticker": series.ticker,
        "name": series.company_name,
        "price": float(row.get("price", float("nan"))),
        "eps": float(row.get("eps_ttm", float("nan"))),
        "pe": pe_trailing,
        "peg": float(peg_5yr) if peg_5yr is not None else peg_yoy,
        "peg_5yr": float(peg_5yr) if peg_5yr is not None else None,
        "peg_yoy": peg_yoy,
        "growth": float(row.get("eps_growth_yoy", float("nan")))
        if pd.notna(row.get("eps_growth_yoy"))
        else None,
    }
    if pd.notna(row.get("price_fair_median")):
        snap["price_fair_median"] = float(row["price_fair_median"])
    pe_hist = df["pe"].dropna() if "pe" in df.columns else pd.Series(dtype=float)
    if not pe_hist.empty:
        snap["pe_hist_median"] = float(pe_hist.median())
        snap["pe_hist_p25"] = float(pe_hist.quantile(0.25))
        snap["pe_hist_p75"] = float(pe_hist.quantile(0.75))
    if market:
        snap["forward_pe"] = market.get("forward_pe")
        snap["forward_eps"] = market.get("forward_eps")
        snap["ev_to_ebitda"] = market.get("ev_to_ebitda")
        snap["target_mean"] = market.get("target_mean")
        snap["target_high"] = market.get("target_high")
        snap["target_low"] = market.get("target_low")
        snap["peg_trailing"] = market.get("peg_trailing")
    return snap


def build_comparison_snapshots(tickers: list[str], horizon_key: str = "5y") -> list[dict]:
    horizon = horizon_for_key(horizon_key)
    rows = []
    for sym in tickers:
        base = build_pe_frame(sym, horizon_for_key("max"))
        sliced = MetricSeries(
            sym,
            "valuation",
            horizon,
            base.frame.copy(),
            base.company_name,
            market=base.market,
        )
        sliced.frame = slice_for_horizon(sliced)
        snap = snapshot_from_series(sliced)
        if snap:
            rows.append(snap)
    return rows


def render_comparison_chart(
    snapshots: list[dict],
    out_path: Path,
    *,
    show_terminal: bool = False,
    console=None,
) -> Path:
    if not snapshots:
        raise ValueError("No ticker data for comparison.")

    labels = [f"{s['ticker']}\n{s['name'][:18]}" for s in snapshots]
    metrics = ["price", "eps", "pe", "peg"]
    titles = [
        "Price ($)",
        "EPS (trailing $)",
        "P/E (trailing)",
        "PEG (5yr expected)",
    ]

    fig, axes = plt.subplots(2, 2, figsize=(FIG_W, FIG_H), dpi=DPI)
    sns.set_theme(style="whitegrid", context="talk")

    for ax, key, title in zip(axes.flat, metrics, titles):
        vals = []
        for s in snapshots:
            v = s.get(key if key != "eps" else "eps")
            if key == "peg" and (v is None or (isinstance(v, float) and pd.isna(v))):
                vals.append(0)
            else:
                vals.append(float(v) if v is not None else 0)
        colors = sns.color_palette("muted", len(labels))
        ax.bar(labels, vals, color=colors, edgecolor="white")
        ax.set_title(title, fontweight="bold")
        ax.set_ylabel(title.split("(")[0].strip())
        ax.tick_params(axis="x", rotation=25)
        if key == "peg":
            ax.axhline(1.0, color="#6C757D", linestyle=":", linewidth=1.2, label="PEG = 1")
            ax.legend(loc="upper right")

    fig.suptitle(
        "E. Valuation comparison — trailing snapshot (same horizon)",
        fontsize=13,
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)

    if show_terminal and console is not None:
        from .display import display_chart_in_terminal

        display_chart_in_terminal(out_path, console)
    return out_path


def format_comparison_table(snapshots: list[dict]):
    """Rich table for terminal display (see summary.build_comparison_table)."""
    from .summary import build_comparison_table

    return build_comparison_table(snapshots)
