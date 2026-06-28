"""Deterministic HTML sections for memos (metrics, DCF, references)."""

from __future__ import annotations

import html
import re
from datetime import date
from typing import Any

from .charts import build_charts_section
from .collect import MemoDataPack

_FILING_HEADER_RE = re.compile(
    r"##\s+\w+\s+—\s+.+?\((\d+-[A-Z]), filed ([^)]+)\)",
    re.IGNORECASE,
)


def _fmt_usd(value: Any) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:.2f}B"
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    return f"${v:,.2f}"


def build_key_metrics_table(facts: dict[str, Any] | None) -> str:
    if not facts or facts.get("error"):
        return "<p><em>Key metrics unavailable.</em></p>"

    snap = facts.get("snapshot") or {}
    pe_hist = facts.get("pe_history_in_window") or {}
    fair = facts.get("fair_value_bands_panel_a") or {}
    changes = facts.get("price_and_eps_changes") or {}

    rows = [
        ("Price", _fmt_usd(snap.get("price_usd"))),
        ("EPS (TTM)", _fmt_usd(snap.get("eps_ttm_usd"))),
        ("P/E (trailing)", str(snap.get("pe_trailing", "—"))),
        ("PEG (5yr expected)", str(snap.get("peg_5yr_expected", "—"))),
        ("EPS growth YoY", f"{snap.get('eps_growth_yoy_pct', '—')}%"),
        ("Earnings yield", f"{snap.get('earnings_yield_pct', '—')}%"),
        ("P/E vs window", f"{pe_hist.get('current_percentile_vs_window', '—')}th %ile"),
        ("P/E median (window)", str(pe_hist.get("median", "—"))),
        ("Fair value (median band)", _fmt_usd(fair.get("price_fair_median_usd"))),
        ("1Y price change", f"{changes.get('full_window_price_pct', '—')}%"),
    ]

    body = "".join(
        f"<tr><td>{html.escape(str(label))}</td>"
        f'<td class="num">{html.escape(str(val))}</td></tr>'
        for label, val in rows
    )
    return (
        '<table class="metrics">'
        "<thead><tr><th>Metric</th><th>Value</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def format_dcf_section(dcf_text: str) -> str:
    text = (dcf_text or "").strip()
    if not text:
        return "<p><em>DCF model unavailable — insufficient FCF or inputs.</em></p>"
    escaped = html.escape(text)
    return (
        '<div class="dcf-block"><pre class="dcf-pre">'
        f"{escaped}</pre></div>"
    )


def _extract_filing_refs(pack: MemoDataPack) -> list[str]:
    refs: list[str] = []
    for block in (pack.mda, pack.bundle):
        for match in _FILING_HEADER_RE.finditer(block or ""):
            form, filed = match.group(1), match.group(2).strip()
            refs.append(f"SEC {form} filed {filed} (EDGAR via Rallies)")
    return refs


def _extract_news_refs(bundle: str, *, limit: int = 5) -> list[str]:
    refs: list[str] = []
    for line in (bundle or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("http") and stripped not in refs:
            refs.append(stripped)
        if len(refs) >= limit:
            break
    return refs


def build_references_section(pack: MemoDataPack) -> str:
    items: list[str] = [
        f"Live market data — Yahoo Finance / yfinance (as of {date.today().isoformat()})",
    ]
    items.extend(_extract_filing_refs(pack))
    items.extend(_extract_news_refs(pack.bundle))

    if pack.dcf and "Quant engine" in pack.dcf:
        items.append("DCF valuation — Rallies quant engine (/dcf)")

    if pack.errors:
        items.append("Collection notes: " + "; ".join(pack.errors[:3]))

    items.append(
        "Expert opinions — Rallies persona panel (Value, Growth, Quant); "
        "not third-party sell-side research."
    )
    items.append(
        "This memo is for research purposes only; not investment advice."
    )

    lis = "".join(f"<li>{html.escape(item)}</li>" for item in items)
    return f'<ol class="references">{lis}</ol>'


def build_deterministic_slots(pack: MemoDataPack) -> dict[str, str]:
    facts = pack.valuation_facts if isinstance(pack.valuation_facts, dict) else {}
    return {
        "charts_section": build_charts_section(pack.ticker),
        "key_metrics_table": build_key_metrics_table(facts),
        "dcf_section": format_dcf_section(pack.dcf),
        "references_section": build_references_section(pack),
    }
