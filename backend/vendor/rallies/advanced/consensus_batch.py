"""Batched multi-persona consensus: 6 tickers per panel, combined master table."""

from __future__ import annotations

import re
from collections import Counter
from typing import Callable

from ..compound.limits import CONSENSUS_BATCH_SIZE, chunk_consensus_batches
from ..compound.models import CompoundContext
from .personas import get_consensus_panel, run_consensus_analysis

_VERDICT_RANK = {
    "strong buy": 5,
    "buy": 4,
    "hold": 3,
    "sell": 2,
    "strong sell": 1,
    "unclear": 0,
}


def _normalize_verdict(verdict: str) -> str:
    v = (verdict or "").strip().lower()
    if not v or v == "unclear" or v == "—":
        return "Unclear"
    labels = {
        "strong sell": "Strong Sell",
        "strong buy": "Strong Buy",
        "sell": "Sell",
        "hold": "Hold",
        "buy": "Buy",
    }
    for key, label in labels.items():
        if key in v:
            return label
    return verdict.strip() or "Unclear"


def _aggregate_verdict(verdicts: list[str]) -> tuple[str, str]:
    """Plurality verdict across experts; average confidence label."""
    cleaned = [_normalize_verdict(v) for v in verdicts if v and v != "—"]
    if not cleaned:
        return "Unclear", "Low"

    counts = Counter(cleaned)
    top = counts.most_common()
    if len(top) == 1:
        winner = top[0][0]
    else:
        tied = [v for v, c in top if c == top[0][1]]
        winner = max(tied, key=lambda x: _VERDICT_RANK.get(x.lower(), 0))

    n = len(cleaned)
    if top[0][1] >= n * 0.6:
        conf = "High"
    elif top[0][1] >= n * 0.4:
        conf = "Medium"
    else:
        conf = "Low"
    return winner, conf


def fetch_quote_facts(
    tickers: list[str],
    data_registry=None,
    agent=None,
) -> dict[str, dict]:
    """Per-ticker quote fields for the master table."""
    facts: dict[str, dict] = {}
    registry = data_registry
    if registry is None and agent is not None:
        registry = getattr(agent, "data_registry", None)

    for ticker in tickers:
        t = ticker.upper().strip()
        row = {"ticker": t, "name": "", "price": None, "pe": None, "sector": ""}
        if registry is None:
            facts[t] = row
            continue
        try:
            q = registry.get_quote(t)
            if isinstance(q, dict) and not q.get("error"):
                row["name"] = (q.get("name") or "").strip()
                row["price"] = q.get("price")
                row["pe"] = q.get("pe")
                row["sector"] = (q.get("sector") or "").strip()
        except Exception:
            pass
        facts[t] = row
    return facts


def _format_price(price) -> str:
    if price is None:
        return "—"
    try:
        return f"${float(price):.2f}"
    except (TypeError, ValueError):
        return "—"


def _format_pe(pe) -> str:
    if pe is None:
        return "—"
    try:
        return f"{float(pe):.2f}"
    except (TypeError, ValueError):
        return "—"


def aggregate_panel_by_ticker(
    panel_results_batches: list[list[dict]],
    tickers: list[str],
) -> dict[str, dict]:
    """Merge expert verdicts across all batches into per-ticker aggregates."""
    by_ticker: dict[str, dict] = {}
    for ticker in tickers:
        t = ticker.upper()
        verdicts: list[str] = []
        snippets: list[str] = []
        for batch in panel_results_batches:
            for entry in batch:
                if entry.get("error"):
                    continue
                td = entry.get("tickers", {}).get(t, {})
                if not td:
                    continue
                v = td.get("verdict", "")
                if v:
                    verdicts.append(v)
                s = (td.get("summary") or "").strip()
                if s:
                    snippets.append(f"{entry.get('name', '?')}: {s[:200]}")

        verdict, confidence = _aggregate_verdict(verdicts)
        by_ticker[t] = {
            "verdict": verdict,
            "confidence": confidence,
            "expert_count": len(verdicts),
            "snippets": snippets,
        }
    return by_ticker


def summarize_batched_consensus_master(
    tickers: list[str],
    batch_summaries: list[str],
    aggregated: dict[str, dict],
    quote_facts: dict[str, dict],
    llm,
) -> str:
    """One LLM pass: unified markdown table + short narrative for all tickers."""
    ticker_list = ", ".join(tickers)
    batch_text = "\n\n---\n\n".join(
        f"### Batch {i + 1}\n\n{s}" for i, s in enumerate(batch_summaries) if s
    )
    facts_lines = []
    for t in tickers:
        q = quote_facts.get(t.upper(), {})
        facts_lines.append(
            f"- {t}: {(q.get('name') or '—')} | {_format_price(q.get('price'))} | "
            f"P/E {_format_pe(q.get('pe'))} | {(q.get('sector') or '—')}"
        )
    agg_lines = []
    for t in tickers:
        a = aggregated.get(t.upper(), {})
        agg_lines.append(
            f"- {t}: panel aggregate {a.get('verdict', '—')} "
            f"({a.get('confidence', '—')}, {a.get('expert_count', 0)} expert reads)"
        )

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are an investment committee moderator synthesizing batched expert panels. "
                "Use only information from the batch summaries and aggregate lines provided. "
                "Do not invent financial figures; use the quote snapshot for price/P/E/sector."
            ),
        },
        {
            "role": "user",
            "content": (
                f"All tickers reviewed: {ticker_list}\n\n"
                f"Quote snapshot:\n" + "\n".join(facts_lines) + "\n\n"
                f"Expert aggregate verdicts:\n" + "\n".join(agg_lines) + "\n\n"
                f"Batched panel summaries:\n\n{batch_text}\n\n"
                "Produce:\n"
                "1. A markdown table with columns: "
                "Ticker | Company | Price | P/E | Sector | Verdict | Confidence | Thesis\n"
                "   One row per ticker. Thesis = 1–2 sentences rationale for the verdict.\n"
                "2. A short **Portfolio takeaway** (3–5 bullets) on agreement, disagreement, "
                "and what to watch.\n"
                "Be specific; reference expert themes from the batches."
            ),
        },
    ]

    from ..llm import LLMError

    try:
        result = llm.prompt(messages, task_type="consensus_summary")
        return str(result) if not isinstance(result, str) else result
    except LLMError as e:
        from ..llm_user_message import format_llm_error_rich

        model = getattr(llm, "last_model", None)
        return format_llm_error_rich(e, model=model)


def build_master_consensus_table_rows(
    tickers: list[str],
    aggregated: dict[str, dict],
    quote_facts: dict[str, dict],
    master_markdown: str,
) -> list[dict]:
    """Structured rows for Rich table; parse master markdown when possible."""
    parsed: dict[str, dict] = {}
    if master_markdown:
        for line in master_markdown.splitlines():
            if "|" not in line or line.strip().startswith("|---"):
                continue
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) < 8:
                continue
            if cells[0].lower() in ("ticker", "---"):
                continue
            ticker = cells[0].upper()
            if re.match(r"^[A-Z][A-Z0-9.\-]{0,9}$", ticker):
                parsed[ticker] = {
                    "company": cells[1],
                    "price": cells[2],
                    "pe": cells[3],
                    "sector": cells[4],
                    "verdict": cells[5],
                    "confidence": cells[6],
                    "thesis": cells[7] if len(cells) > 7 else "",
                }

    rows: list[dict] = []
    for ticker in tickers:
        t = ticker.upper()
        q = quote_facts.get(t, {})
        a = aggregated.get(t, {})
        p = parsed.get(t, {})
        rows.append(
            {
                "ticker": t,
                "company": p.get("company") or q.get("name") or "—",
                "price": p.get("price") or _format_price(q.get("price")),
                "pe": p.get("pe") or _format_pe(q.get("pe")),
                "sector": p.get("sector") or q.get("sector") or "—",
                "verdict": p.get("verdict") or a.get("verdict", "—"),
                "confidence": p.get("confidence") or a.get("confidence", "—"),
                "thesis": p.get("thesis")
                or (
                    " ".join(a.get("snippets", [])[:2])[:280]
                    if a.get("snippets")
                    else "—"
                ),
            }
        )
    return rows


def run_batched_consensus_analysis(
    tickers: list[str],
    llm,
    *,
    data_registry=None,
    agent=None,
    compound_ctx: CompoundContext | None = None,
    status_callback: Callable[[str], None] | None = None,
    on_persona_complete: Callable | None = None,
    on_batch_complete: Callable[[int, int, list[str], list[dict], str], None] | None = None,
    panel: list[dict] | None = None,
    ranking_instruction: str = "",
) -> tuple[list[list[dict]], list[str], str, list[dict]]:
    """
    Run consensus in batches of CONSENSUS_BATCH_SIZE tickers.

    Returns (panel_results_per_batch, batch_summaries, master_markdown, table_rows).
    """
    tickers = [t.upper().strip() for t in tickers if t and t.strip()]
    if not tickers:
        return [], [], "[yellow]No tickers provided.[/yellow]", []

    batches = chunk_consensus_batches(tickers, compound_ctx=compound_ctx)
    if panel is None:
        panel = get_consensus_panel()

    all_panel_batches: list[list[dict]] = []
    batch_summaries: list[str] = []
    n_batches = len(batches)

    for batch_idx, batch in enumerate(batches, start=1):
        if callable(status_callback):
            status_callback(
                f"[bold]Batch {batch_idx}/{n_batches}[/bold] — "
                f"panel analyzing {', '.join(batch)} ({len(batch)} tickers)…"
            )

        def _on_persona(result, idx, total, _batch=batch):
            if callable(on_persona_complete):
                on_persona_complete(result, idx, total, _batch)

        panel_results, summary = run_consensus_analysis(
            batch,
            llm,
            data_registry=data_registry,
            agent=agent,
            live_data_block=None,
            status_callback=status_callback,
            on_persona_complete=_on_persona,
            panel=panel,
            ranking_instruction=ranking_instruction,
        )
        all_panel_batches.append(panel_results)
        batch_summaries.append(summary)
        if callable(on_batch_complete):
            on_batch_complete(batch_idx, n_batches, batch, panel_results, summary)

    if callable(status_callback):
        status_callback(
            f"Building master table for {len(tickers)} tickers "
            f"from {n_batches} batch{'es' if n_batches != 1 else ''}…"
        )

    quote_facts = fetch_quote_facts(tickers, data_registry=data_registry, agent=agent)
    aggregated = aggregate_panel_by_ticker(all_panel_batches, tickers)
    master = summarize_batched_consensus_master(
        tickers, batch_summaries, aggregated, quote_facts, llm
    )
    table_rows = build_master_consensus_table_rows(
        tickers, aggregated, quote_facts, master
    )
    return all_panel_batches, batch_summaries, master, table_rows


def needs_batched_consensus(ticker_count: int, batch_size: int = CONSENSUS_BATCH_SIZE) -> bool:
    return ticker_count > batch_size
