"""Plain-text valuation summary for /chart (readable in the terminal)."""

from __future__ import annotations

import pandas as pd
from rich.table import Table

from .data import MetricSeries, peg_for_display, validate_series_frame


def build_valuation_summary(series: MetricSeries) -> str:
    df = series.frame.dropna(subset=["pe"])
    if df.empty:
        return "Not enough trailing data to summarize this horizon."

    pe = df["pe"].astype(float)
    pe_now = float(pe.iloc[-1])
    if series.market and series.market.get("pe_trailing") is not None:
        pe_now = float(series.market["pe_trailing"])
    pe_med = float(pe.median())
    p25 = float(pe.quantile(0.25))
    p75 = float(pe.quantile(0.75))

    last = df.iloc[-1]
    _, peg_yoy_label = peg_for_display(last)
    peg_yoy_raw = last.get("peg_raw", last.get("peg"))
    peg_yoy_for_rules = float(peg_yoy_raw) if pd.notna(peg_yoy_raw) else None
    peg_5yr = None
    growth_5yr = None
    if series.market:
        peg_5yr = series.market.get("peg_trailing")
        growth_5yr = series.market.get("growth_5yr_expected_pct")
    peg_5yr_label = f"{float(peg_5yr):.2f}" if peg_5yr is not None else "—"

    growth_now = None
    if "eps_growth_yoy" in df.columns:
        g = df["eps_growth_yoy"].dropna()
        if not g.empty:
            growth_now = float(g.iloc[-1])

    price_now = float(df["price"].iloc[-1])
    eps_now = float(df["eps_ttm"].iloc[-1])
    if series.market and series.market.get("eps_trailing") is not None:
        eps_now = float(series.market["eps_trailing"])
    dr = f"{df.index.min().date()} → {df.index.max().date()}"

    sections: list[str] = [
        f"{series.company_name} ({series.ticker})",
        f"{series.horizon.label} · {dr} · trailing metrics only (charts use the same data)",
        "",
        "What this means",
        _plain_meaning_blurb(),
        "",
        "Snapshot (latest trading day)",
        f"  Price ${price_now:.2f}",
        f"  EPS trailing four quarters ${eps_now:.2f}",
        f"  P/E {pe_now:.1f}  (price ÷ trailing four-quarter EPS; Yahoo key statistics)",
        f"  PEG {peg_5yr_label}  (5yr expected — Yahoo Finance pegRatio)",
        f"  PEG (YoY) {peg_yoy_label}  (P/E ÷ YoY EPS growth %; panel D/E only)",
        "",
        "P/E vs this stock's past (panel C)",
        f"  {_valuation_label(pe_now, pe_med, p25, p75)}",
        f"  Median P/E in window: {pe_med:.1f}  ·  typical range (25th–75th): {p25:.1f}–{p75:.1f}",
        "",
        "Price vs earnings",
        f"  Full window: {_price_eps_dynamics(df)}",
        f"  Last ~3 months: {_recent_price_eps(df)}",
    ]

    if peg_5yr is not None and growth_5yr is not None:
        sections.extend(
            [
                "",
                "PEG (5yr expected — Yahoo key statistics)",
                f"  {peg_5yr_label} implies ~{growth_5yr:.1f}% long-term EPS growth (P/E ÷ PEG).",
            ]
        )
    if peg_yoy_for_rules is not None and growth_now is not None and growth_now > 0:
        sections.extend(
            [
                "",
                "PEG YoY (panel D — not Yahoo 5yr PEG)",
                f"  {_peg_interpretation(pe_now, peg_yoy_for_rules, growth_now)}",
                f"  YoY EPS growth: {growth_now:+.1f}%",
            ]
        )
    elif growth_now is not None and growth_now <= 0:
        sections.append("")
        sections.append("PEG YoY (panel D)")
        sections.append("  EPS growth is weak or negative — YoY PEG is not meaningful.")

    ey = (eps_now / price_now * 100) if price_now else None
    if ey is not None:
        sections.extend(["", "Earnings yield", f"  {ey:.2f}%  (EPS ÷ price, inverse of P/E)"])

    lynch = _lynch_position(last, price_now)
    if lynch:
        sections.extend(["", "Fair-value bands (panel A)", f"  {lynch}"])

    if series.market:
        sections.extend(["", "Market snapshot (panels F–G / yfinance)"])
        sections.extend(_format_market_snapshot(series.market, price_now))

    warnings = validate_series_frame(df, series.horizon.label)
    if warnings:
        sections.extend(["", "Data quality"])
        sections.extend(f"  · {w}" for w in warnings)

    sections.extend(["", "Chart panels", *_panel_guides()])
    sections.extend(
        ["", "Takeaways", *_interpretation_rules(pe_now, peg_yoy_for_rules, growth_now, df)]
    )
    return "\n".join(sections)


def build_summary(series: MetricSeries, metric: str = "valuation") -> str:
    return build_valuation_summary(series)


def build_comparison_table(snapshots: list[dict]) -> Table:
    table = Table(
        title="Valuation snapshot (Yahoo Finance key statistics parity)",
        show_header=True,
    )
    table.add_column("Ticker", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("EPS TTM", justify="right")
    table.add_column("P/E", justify="right")
    table.add_column("Fwd P/E", justify="right")
    table.add_column("PEG 5yr", justify="right")
    table.add_column("EPS Gr YoY", justify="right")
    for s in snapshots:
        peg = f"{s['peg']:.2f}" if s.get("peg") is not None and not pd.isna(s["peg"]) else "—"
        fpe = (
            f"{s['forward_pe']:.1f}"
            if s.get("forward_pe") is not None and not pd.isna(s["forward_pe"])
            else "—"
        )
        gr = (
            f"{s['growth']:+.1f}"
            if s.get("growth") is not None and not pd.isna(s["growth"])
            else "—"
        )
        table.add_row(
            s["ticker"],
            f"${s['price']:.2f}",
            f"${s['eps']:.2f}",
            f"{s['pe']:.1f}",
            fpe,
            peg,
            gr,
        )
    return table


def _plain_meaning_blurb() -> str:
    return (
        "  P/E: how many dollars the market pays per $1 of trailing earnings. "
        "Lower vs this stock's own history often means cheaper; compare to growth and forward estimates.\n"
        "  EPS: sum of the last four quarterly earnings per share — earnings power today.\n"
        "  PEG (5yr expected): Yahoo Finance key statistic — trailing P/E ÷ analyst 5-year EPS growth.\n"
        "  PEG (YoY): P/E ÷ YoY quarterly EPS growth (panel D only; can differ sharply from 5yr PEG).\n"
        "  Panel A shows price vs a fair band derived from EPS × typical historical P/E."
    )


def _valuation_label(current: float, median: float, p25: float, p75: float) -> str:
    if current <= p25:
        return "Below the 25th percentile — historically cheap in this window."
    if current >= p75:
        return "Above the 75th percentile — historically rich in this window."
    if abs(current - median) / max(median, 1) < 0.1:
        return "Near the period median — roughly fair vs own history."
    if current < median:
        return "Below median — modestly cheaper than usual for this window."
    return "Above median — higher multiple than usual for this window."


def _pct_change(series: pd.Series) -> float:
    if len(series) < 2 or series.iloc[0] == 0:
        return 0.0
    return (float(series.iloc[-1]) / float(series.iloc[0]) - 1) * 100


def _price_eps_dynamics(df: pd.DataFrame) -> str:
    if len(df) < 2:
        return "Insufficient history."
    price_ret = _pct_change(df["price"])
    eps_ret = _pct_change(df["eps_ttm"])
    return _classify_price_eps(price_ret, eps_ret, label="window")


def _recent_price_eps(df: pd.DataFrame, days: int = 63) -> str:
    if len(df) < 10:
        return "Insufficient recent data."
    tail = df.iloc[-min(days, len(df)) :]
    if len(tail) < 5:
        return "Insufficient recent data."
    price_ret = _pct_change(tail["price"])
    eps_ret = _pct_change(tail["eps_ttm"])
    return _classify_price_eps(price_ret, eps_ret, label="recent stretch")


def _classify_price_eps(price_ret: float, eps_ret: float, label: str) -> str:
    if eps_ret > price_ret + 12:
        return (
            f"price {price_ret:+.1f}%, EPS {eps_ret:+.1f}% — earnings rose faster than price; "
            "trailing P/E likely fell."
        )
    if price_ret > eps_ret + 12:
        return (
            f"price {price_ret:+.1f}%, EPS {eps_ret:+.1f}% — price rose faster than earnings; "
            "trailing P/E likely rose."
        )
    return f"price {price_ret:+.1f}%, EPS {eps_ret:+.1f}% — moved broadly together."


def _peg_interpretation(pe: float, peg: float, growth: float) -> str:
    if growth <= 0:
        return "Non-positive growth — rely on P/E and cash flow, not PEG."
    if peg < 1 and pe > 15:
        return f"P/E {pe:.1f} with PEG {peg:.2f} — growth often supports the multiple."
    if peg > 2.5 and pe > 20:
        return (
            f"P/E {pe:.1f} with PEG {peg:.2f} — multiple may be ahead of recent YoY growth."
        )
    if pe < 15 and growth < 5:
        return f"P/E {pe:.1f} with slow growth ({growth:+.1f}%) — market may expect weak earnings."
    return f"P/E {pe:.1f} and PEG {peg:.2f} vs {growth:+.1f}% YoY EPS growth."


def _lynch_position(row: pd.Series, price_now: float) -> str | None:
    low = row.get("price_fair_low")
    high = row.get("price_fair_high")
    med = row.get("price_fair_median")
    if pd.isna(low) or pd.isna(high) or pd.isna(med):
        return None
    low, high, med = float(low), float(high), float(med)
    if price_now <= low:
        return "Price is below the low fair band (25th-percentile P/E × EPS)."
    if price_now >= high:
        return "Price is above the high fair band (75th-percentile P/E × EPS)."
    if abs(price_now - med) / max(med, 1) < 0.08:
        return "Price is near the median fair-value line."
    if price_now < med:
        return "Price is inside the band, below median fair value."
    return "Price is inside the band, above median fair value."


def _format_market_snapshot(market: dict, price_now: float) -> list[str]:
    lines: list[str] = []
    fpe = market.get("forward_pe")
    feps = market.get("forward_eps")
    tpe = market.get("pe_trailing")
    if fpe is not None:
        lines.append(f"  Forward P/E: {float(fpe):.1f}")
    if tpe is not None and fpe is not None:
        if market.get("forward_pe_below_trailing"):
            lines.append(
                f"  Forward P/E below trailing ({fpe:.1f} vs {tpe:.1f}) — growth expected"
            )
        else:
            lines.append(f"  Forward P/E vs trailing: {fpe:.1f} vs {tpe:.1f}")
    if feps is not None:
        lines.append(f"  Forward EPS: ${float(feps):.2f}")
    ev = market.get("ev_to_ebitda")
    if ev is not None:
        lines.append(f"  EV/EBITDA: {float(ev):.1f}")
    for label, key in (
        ("Target low", "target_low"),
        ("Target mean", "target_mean"),
        ("Target high", "target_high"),
    ):
        v = market.get(key)
        if v is not None:
            lines.append(f"  {label}: ${float(v):.2f}")
    upside = market.get("target_upside_pct")
    if upside is not None:
        lines.append(f"  Upside to mean target: {upside:+.1f}%")
    if not lines:
        lines.append("  No market snapshot from data provider.")
    return lines


def _panel_guides() -> list[str]:
    return [
        "  A — Price vs fair band (EPS × historical P/E 25th–75th) and median fair line",
        "  B — Price vs trailing EPS",
        "  C — Trailing P/E with historical percentile band",
        "  D — PEG YoY (P/E ÷ YoY EPS growth; NOT Yahoo 5yr PEG; capped at 12 on chart)",
        "  E — P/E vs EPS growth scatter (YoY PEG = 1 diagonal); use --no-scatter to hide",
        "  F — Trailing vs forward P/E (stocks_valuation notebook)",
        "  G — Analyst target low / mean / high vs current price",
    ]


def _interpretation_rules(
    pe_now: float,
    peg_now: float | None,
    growth_now: float | None,
    df: pd.DataFrame,
) -> list[str]:
    rules: list[str] = []
    if peg_now is not None and growth_now is not None and growth_now > 0:
        if pe_now > 25 and peg_now < 1:
            rules.append("  · High P/E but low PEG — strong growth may justify the multiple.")
        if pe_now > 25 and peg_now > 2.5:
            rules.append("  · High P/E and high PEG — multiple may be ahead of recent YoY growth.")
        if pe_now <= float(df["pe"].quantile(0.25)) and peg_now > 2.5:
            rules.append(
                "  · P/E is low vs history but PEG is high — YoY growth slowed after past "
                "earnings surges; read forward P/E and panel E (5y CAGR)."
            )
    if growth_now is not None and growth_now < 3 and pe_now < 12:
        rules.append("  · Low P/E and weak growth — market may expect earnings weakness.")

    if len(df) >= 63:
        tail = df.iloc[-63:]
        p_chg = _pct_change(tail["price"])
        e_chg = _pct_change(tail["eps_ttm"])
        if p_chg > 8 and e_chg < 3:
            rules.append("  · Last ~3 months: price up, EPS flat — watch for P/E expansion.")
        elif e_chg > p_chg + 10:
            rules.append("  · Last ~3 months: EPS grew faster than price — P/E compression likely.")

    if not rules:
        rules.append("  · Use panels A–C together; one metric alone is not enough.")
    return rules
