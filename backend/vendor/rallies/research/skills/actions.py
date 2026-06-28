"""Executable helpers referenced by skills (not just markdown checklists)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from ..batch.ticker_bundle import parallel_quote_sec_bundle
from ..filing.section_fetch import fetch_filing_section, format_filing_section
from ..meta.research_fetch import research_fetch
from ..paths import memos_dir


def _strip_rich(text: str) -> str:
    return re.sub(r"\[/?[^\]]+\]", "", text)


def run_dcf_quant(
    ticker: str,
    *,
    growth_rate: float = 0.10,
    wacc: float = 0.09,
    terminal_growth: float = 0.03,
) -> str:
    """
    Run rallies quant DCF (same engine as /dcf). Returns plain-text summary.
    """
    ticker = ticker.upper().strip()
    try:
        import yfinance as yf

        from ...quant.dcf import dcf_valuation
    except ImportError:
        return "DCF requires yfinance and numpy: pip install 'rallies[sources]' numpy"

    t = yf.Ticker(ticker)
    info = t.info or {}
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    from ...quant.dcf import fetch_free_cash_flow_yfinance

    from ...metric_units import normalize_rate_decimal

    growth_rate = normalize_rate_decimal(growth_rate)
    wacc = normalize_rate_decimal(wacc)
    terminal_growth = normalize_rate_decimal(terminal_growth)

    fcf, fcf_source = fetch_free_cash_flow_yfinance(t)
    shares = info.get("sharesOutstanding")
    cash = info.get("totalCash") or 0
    debt = info.get("totalDebt") or 0

    fair_value, details = dcf_valuation(
        ticker=ticker,
        free_cash_flow=fcf,
        growth_rate=growth_rate,
        terminal_growth=terminal_growth,
        wacc=wacc,
        shares_outstanding=shares,
        cash_and_equivalents=cash,
        total_debt=debt,
        current_price=price,
        fcf_source=fcf_source,
    )
    if fair_value is None and "no positive" in details.lower():
        return _strip_rich(details)
    body = _strip_rich(details)
    return f"{body}\n\n(Quant engine — same as /dcf {ticker} {growth_rate} {wacc})"


def gather_equity_bundle(registry: Any, ticker: str, *, include_risk_excerpt: bool = True) -> str:
    """
    One-shot data pull for memo / deep-dive skills: quote, financials, news, SEC, optional risks.
    """
    ticker = ticker.upper().strip()
    blocks: list[str] = [f"# Equity data bundle — {ticker}"]

    blocks.append(research_fetch(registry, ticker, "quote"))
    blocks.append(research_fetch(registry, ticker, "financials and margins"))
    blocks.append(research_fetch(registry, ticker, "news"))
    blocks.append(research_fetch(registry, ticker, "insider"))

    if registry:
        sec_records = parallel_quote_sec_bundle(registry, ticker)
        for rec in sec_records:
            if rec.tool_name == "edgartools_sec_filings" and rec.line:
                blocks.append(rec.line)

    if include_risk_excerpt:
        risk = fetch_filing_section(ticker, "risk factors")
        if not risk.get("error") and risk.get("text"):
            excerpt = str(risk["text"])[:6000]
            blocks.append(
                f"## Risk factors excerpt ({risk.get('form')} {risk.get('filing_date')})\n{excerpt}"
            )

    business = fetch_filing_section(ticker, "business description")
    if not business.get("error") and business.get("text"):
        excerpt = str(business["text"])[:4000]
        blocks.append(
            f"## Business excerpt ({business.get('form')} {business.get('filing_date')})\n{excerpt}"
        )

    return "\n\n".join(blocks)


def write_memo_html(
    ticker: str,
    direction: str,
    html_content: str,
    *,
    suffix: str | None = None,
) -> dict[str, Any]:
    """Write memo HTML to .rallies/memos/. Returns path metadata."""
    ticker = ticker.upper().strip()
    direction = direction.upper().strip()
    if direction not in ("LONG", "SHORT"):
        direction = "LONG" if direction.startswith("L") else "SHORT"

    memos_dir().mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    extra = f"_{suffix}" if suffix else ""
    filename = f"{ticker}_{direction}_{stamp}{extra}.html"
    path = memos_dir() / filename
    path.write_text(html_content, encoding="utf-8")
    return {
        "path": str(path),
        "filename": filename,
        "ticker": ticker,
        "direction": direction,
    }


def load_memo_template() -> str:
    template_path = Path(__file__).resolve().parent / "builtin" / "write-memo" / "memo-template.html"
    if template_path.is_file():
        return template_path.read_text(encoding="utf-8")
    return "<html><body>{{body}}</body></html>"


def render_memo_template(slots: dict[str, str]) -> str:
    html = load_memo_template()
    for key, value in slots.items():
        html = html.replace(f"{{{{{key}}}}}", value or "")
    return html
