"""
Live market prefetch for /ask, /debate, and /consensus (additive).

Reuses Agent.compare prefetch (quotes + financials) and SEC bundle for single tickers.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..compound.limits import PERSONA_INLINE_TICKER_MAX
from ..ticker_identify import identify_query_tickers


def resolve_persona_tickers(
    question: str,
    explicit_tickers: list[str] | None = None,
    *,
    max_tickers: int | None = PERSONA_INLINE_TICKER_MAX,
) -> list[str]:
    """Tickers from explicit args and/or question text.

    ``max_tickers=None`` keeps the full explicit list (e.g. compound /watchlist).
    Default cap applies only when inferring from casual /ask text.
    """
    merged: list[str] = []
    for t in explicit_tickers or []:
        if t and str(t).strip():
            merged.append(str(t).strip().upper())
    merged.extend(identify_query_tickers(question or ""))
    out = list(dict.fromkeys(merged))
    if max_tickers is None:
        return out
    return out[:max_tickers]


def format_persona_live_data_prefix(block: str) -> str:
    """Wrap fetched data with the same instruction tone as planner action steps."""
    text = (block or "").strip()
    if not text:
        return ""
    today = date.today().isoformat()
    return (
        f"## CRITICAL — Live market data (retrieved {today})\n"
        "The following was fetched from rallies data sources right now. "
        "You MUST use these exact figures for price, multiples, revenue, and filings. "
        "Do NOT substitute training-data prices or stale fundamentals. "
        "Do NOT tell the user to fetch data — analyze using what is below.\n\n"
        f"{text}\n\n---\n\n"
    )


def _record_prefetch(
    research_session: Any | None,
    tool_name: str,
    query_key: str,
    payload: str,
) -> None:
    if research_session and payload:
        research_session.record_data_tool(
            tool_name,
            {"query": query_key},
            payload,
            query_key=query_key,
        )


def _prefetch_without_agent(
    registry: Any,
    tickers: list[str],
    research_session: Any | None = None,
    *,
    max_tickers: int | None = PERSONA_INLINE_TICKER_MAX,
) -> str:
    """Quote + financials when no Agent instance (tests / edge cases)."""
    yfs = registry.get_source("yfinance") if registry else None
    if not yfs:
        return ""
    lines = [
        "## Prefetched live market data",
        "Use these exact figures. Do not ask the user to fetch more data.",
    ]
    use = tickers if max_tickers is None else tickers[:max_tickers]
    from ..quotes import format_yfinance_quote_line

    for ticker in use:
        data = yfs.get_quote(ticker)
        if data and "error" not in data:
            quote_line = format_yfinance_quote_line(data)
            lines.append(quote_line)
            _record_prefetch(
                research_session, "yfinance_quote", f"persona | {ticker}", quote_line
            )
        fin = yfs.get_financials(ticker, years=3)
        if fin and "error" not in fin:
            rev_row = net_row = None
            for r in fin.get("rows", []):
                if r["label"] == "Total Revenue":
                    rev_row = r
                if r["label"] == "Net Income":
                    net_row = r
            fin_lines = [f"--- {ticker} Financials ---"]
            if rev_row:
                vals = []
                for i, v in enumerate(rev_row["values"]):
                    period = fin["periods"][i] if i < len(fin["periods"]) else ""
                    if v:
                        vals.append(f"{period}: ${v/1e9:.2f}B")
                fin_lines.append("Revenue: " + " | ".join(vals))
            if net_row:
                vals = []
                for i, v in enumerate(net_row["values"]):
                    period = fin["periods"][i] if i < len(fin["periods"]) else ""
                    if v:
                        vals.append(f"{period}: ${v/1e9:.2f}B")
                fin_lines.append("Net Income: " + " | ".join(vals))
            if len(fin_lines) > 1:
                block = "\n".join(fin_lines)
                lines.append(block)
                _record_prefetch(
                    research_session,
                    "yfinance_financials",
                    f"persona | {ticker}",
                    block,
                )
    return "\n".join(lines) if len(lines) > 2 else ""


def _append_sec_filings(
    registry: Any,
    ticker: str,
    research_session: Any | None = None,
) -> str:
    """Recent 8-K list for one ticker (quote/financials come from compare prefetch)."""
    from ..research.batch.ticker_bundle import parallel_quote_sec_bundle

    records = parallel_quote_sec_bundle(registry, ticker)
    sec_lines = [r.line for r in records if r.tool_name == "edgartools_sec_filings" and r.line]
    for rec in records:
        if rec.tool_name == "edgartools_sec_filings" and rec.line:
            _record_prefetch(
                research_session,
                rec.tool_name,
                f"persona | {rec.query_suffix}",
                rec.line,
            )
    return "\n".join(sec_lines)


def build_persona_live_data_block(
    tickers: list[str] | None = None,
    *,
    question: str = "",
    max_tickers: int | None = PERSONA_INLINE_TICKER_MAX,
    data_registry: Any | None = None,
    agent: Any | None = None,
    research_session: Any | None = None,
) -> str:
    """
    Build a single live-data block for persona commands.

    Prefer Agent.build_compare_prefetch when agent is available; fall back to
    direct yfinance reads. For one ticker, append recent SEC 8-K filings.
    """
    if tickers:
        resolved = list(
            dict.fromkeys(str(t).strip().upper() for t in tickers if t and str(t).strip())
        )
        if max_tickers is not None:
            resolved = resolved[:max_tickers]
    else:
        resolved = resolve_persona_tickers(question, None, max_tickers=max_tickers)
    if not resolved:
        return ""

    registry = (getattr(agent, "data_registry", None) if agent else None) or data_registry
    if not registry:
        return ""

    prev_session = getattr(agent, "research_session", None) if agent else None
    if agent is not None and research_session is not None:
        agent.set_research_session(research_session)

    try:
        if agent is not None and hasattr(agent, "build_compare_prefetch"):
            core = agent.build_compare_prefetch(resolved, max_tickers=max_tickers)
        else:
            core = _prefetch_without_agent(
                registry, resolved, research_session, max_tickers=max_tickers
            )

        if len(resolved) == 1:
            sec = _append_sec_filings(registry, resolved[0], research_session)
            if sec:
                core = f"{core}\n{sec}".strip() if core else sec

        if not core.strip():
            core = _minimal_quote_fallback(registry, resolved, max_tickers=max_tickers)

        if not core.strip():
            return ""

        from ..research.tool_results import spill_if_large

        spilled = spill_if_large(core, label="persona_prefetch")
        if research_session and spilled.spilled:
            research_session.scratchpad.add_thinking(
                f"Spilled persona prefetch ({spilled.original_chars} chars) to {spilled.path}"
            )
        return format_persona_live_data_prefix(spilled.text)
    finally:
        if agent is not None and research_session is not None:
            agent.set_research_session(prev_session)


def _minimal_quote_fallback(
    registry: Any,
    tickers: list[str],
    *,
    max_tickers: int | None = PERSONA_INLINE_TICKER_MAX,
) -> str:
    """Last-resort one-line quotes if full prefetch returned nothing."""
    yfs = registry.get_source("yfinance") if registry else None
    if not yfs:
        return ""
    lines = ["Market context (limited — full prefetch unavailable):"]
    use = tickers if max_tickers is None else tickers[:max_tickers]
    from ..quotes import format_yfinance_quote_line

    for ticker in use:
        data = yfs.get_quote(ticker)
        if not data or data.get("error"):
            continue
        lines.append(format_yfinance_quote_line(data))
    return "\n".join(lines) if len(lines) > 1 else ""
