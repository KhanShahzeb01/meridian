"""Structured valuation facts for LLM chart analysis (no full time series)."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from .data import MetricSeries, peg_for_display, validate_series_frame


def _pct_change(series: pd.Series) -> float | None:
    s = series.dropna()
    if len(s) < 2 or float(s.iloc[0]) == 0:
        return None
    return round((float(s.iloc[-1]) / float(s.iloc[0]) - 1) * 100, 2)


def _safe_float(v) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None


def build_valuation_facts(series: MetricSeries) -> dict[str, Any]:
    """Compact facts derived from the same data shown on /chart panels."""
    df = series.frame.dropna(subset=["pe"])
    if df.empty:
        return {"error": "No trailing P/E data in window"}

    pe = df["pe"].astype(float)
    pe_now = float(pe.iloc[-1])
    last = df.iloc[-1]
    peg_yoy, peg_yoy_label = peg_for_display(last)
    peg_5yr = None
    growth_5yr = None
    if series.market:
        peg_5yr = _safe_float(series.market.get("peg_trailing"))
        growth_5yr = _safe_float(series.market.get("growth_5yr_expected_pct"))

    growth_yoy = _safe_float(last.get("eps_growth_yoy"))
    growth_5y = _safe_float(last.get("eps_growth_5y_cagr"))
    price_now = float(last["price"])
    eps_now = float(last["eps_ttm"])

    facts: dict[str, Any] = {
        "ticker": series.ticker,
        "company_name": series.company_name,
        "horizon": series.horizon.label,
        "window_start": str(df.index.min().date()),
        "window_end": str(df.index.max().date()),
        "trading_days": len(df),
        "metrics_note": (
            "Trailing P/E and EPS TTM use four-quarter GAAP diluted EPS from statements. "
            "peg_5yr_expected matches Yahoo Finance key statistics (pegRatio). "
            "peg_yoy is P/E ÷ YoY EPS growth — different metric, shown on panel D only."
        ),
        "snapshot": {
            "price_usd": round(price_now, 2),
            "eps_ttm_usd": round(eps_now, 2),
            "pe_trailing": round(pe_now, 2),
            "peg_5yr_expected": peg_5yr,
            "growth_5yr_expected_pct": growth_5yr,
            "peg_yoy": peg_yoy,
            "peg_yoy_display_note": peg_yoy_label,
            "eps_growth_yoy_pct": growth_yoy,
            "eps_growth_5y_cagr_pct": growth_5y,
            "earnings_yield_pct": round(eps_now / price_now * 100, 2) if price_now else None,
        },
        "pe_history_in_window": {
            "median": round(float(pe.median()), 2),
            "p25": round(float(pe.quantile(0.25)), 2),
            "p75": round(float(pe.quantile(0.75)), 2),
            "min": round(float(pe.min()), 2),
            "max": round(float(pe.max()), 2),
            "current_percentile_vs_window": round(
                float((pe <= pe_now).sum()) / len(pe) * 100, 1
            ),
        },
        "price_and_eps_changes": {
            "full_window_price_pct": _pct_change(df["price"]),
            "full_window_eps_ttm_pct": _pct_change(df["eps_ttm"]),
            "last_63d_price_pct": _pct_change(df["price"].iloc[-63:]),
            "last_63d_eps_ttm_pct": _pct_change(df["eps_ttm"].iloc[-63:]),
        },
        "fair_value_bands_panel_a": {
            "price_fair_low_usd": _safe_float(last.get("price_fair_low")),
            "price_fair_median_usd": _safe_float(last.get("price_fair_median")),
            "price_fair_high_usd": _safe_float(last.get("price_fair_high")),
            "interpretation": (
                "Bands = trailing EPS × historical P/E percentiles in this window "
                "(Peter Lynch / fair-value style)."
            ),
        },
        "chart_panels": {
            "A": "Price vs fair band (EPS × P/E 25th–75th) and median fair line",
            "B": "Price vs trailing EPS",
            "C": "Trailing P/E with historical percentile band",
            "D": "PEG YoY (P/E ÷ YoY EPS growth; NOT Yahoo 5yr PEG; capped at 12)",
            "E": "P/E vs YoY EPS growth scatter; diagonal is YoY PEG=1",
        },
        "data_quality_warnings": validate_series_frame(df, series.horizon.label),
    }

    if series.market:
        m = series.market
        facts["market_snapshot"] = {
            k: _safe_float(v) if isinstance(v, (int, float)) else v
            for k, v in m.items()
        }
        if m.get("forward_pe_below_trailing") is not None:
            facts["market_snapshot"]["forward_pe_below_trailing"] = m[
                "forward_pe_below_trailing"
            ]

    # Year-ago comparison for narrative context
    if len(df) >= 252:
        row_1y = df.iloc[-252]
        facts["roughly_one_year_ago"] = {
            "price_usd": _safe_float(row_1y.get("price")),
            "eps_ttm_usd": _safe_float(row_1y.get("eps_ttm")),
            "pe_trailing": _safe_float(row_1y.get("pe")),
        }

    return facts


def format_facts_for_llm(facts: dict[str, Any]) -> str:
    return json.dumps(facts, indent=2, default=str)


def build_comparison_facts(snapshots: list[dict], horizon_label: str) -> dict[str, Any]:
    return {
        "horizon": horizon_label,
        "tickers": snapshots,
        "metrics_note": "Trailing snapshot at same horizon for each ticker.",
    }
