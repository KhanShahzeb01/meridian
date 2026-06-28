"""Lightweight expert panel for investment memos (3 personas)."""

from __future__ import annotations

import html
from typing import Any

from .markdown_html import markdown_to_html, normalize_verdict_label, verdict_badge_html

# Value, growth, quant — enough diversity without full 7-expert consensus cost.
MEMO_EXPERT_KEYS: tuple[str, ...] = ("buffett", "lynch", "simons")


def _format_expert_block(result: dict[str, Any], ticker: str) -> str:
    name = html.escape(str(result.get("name") or result.get("key") or "Expert"))
    category = html.escape(str(result.get("category") or ""))
    if result.get("error"):
        return (
            f'<div class="expert-card">'
            f'<div class="expert-header"><h3>{name}</h3></div>'
            f'<p class="expert-meta">{category}</p>'
            f'<p class="expert-error">{html.escape(str(result["error"]))}</p>'
            f"</div>"
        )

    tdata = (result.get("tickers") or {}).get(ticker.upper(), {})
    raw = str(result.get("raw") or "").strip()
    verdict_src = str(tdata.get("verdict") or raw[:400])
    verdict = normalize_verdict_label(verdict_src)
    confidence = str(tdata.get("confidence") or "Medium").strip()
    analysis_md = raw or str(tdata.get("summary") or "")
    analysis_html = markdown_to_html(analysis_md)

    return (
        f'<div class="expert-card">'
        f'<div class="expert-header">'
        f"<h3>{name}</h3>"
        f"{verdict_badge_html(verdict, confidence)}"
        f"</div>"
        f'<p class="expert-meta">{category}</p>'
        f'<details class="expert-analysis" open>'
        f"<summary>Full analysis</summary>"
        f'<div class="expert-body">{analysis_html}</div>'
        f"</details>"
        f"</div>"
    )


def collect_memo_expert_opinions(
    ticker: str,
    llm: Any,
    *,
    registry: Any = None,
    agent: Any = None,
    console: Any = None,
    live_data_block: str = "",
) -> str:
    """
    Run a 3-expert memo panel and return HTML for the template.

    Reuses prefetched live data when provided to avoid duplicate fetches.
    """
    from rallies.advanced.personas import ask_persona_consensus

    ticker = ticker.upper().strip()
    blocks: list[str] = []

    def _emit(msg: str) -> None:
        if console is not None:
            console.print(f"[bright_black]{msg}[/bright_black]")

    if not live_data_block and registry is not None:
        from rallies.advanced.persona_market import build_persona_live_data_block

        live_data_block = build_persona_live_data_block(
            [ticker],
            max_tickers=1,
            data_registry=registry,
            agent=agent,
        )

    for idx, key in enumerate(MEMO_EXPERT_KEYS, start=1):
        _emit(f"Memo experts · {idx}/{len(MEMO_EXPERT_KEYS)} ({key})…")
        try:
            result = ask_persona_consensus(
                key,
                [ticker],
                llm,
                live_data_block=live_data_block,
                agent=agent,
            )
        except Exception as exc:
            result = {"key": key, "name": key, "error": str(exc), "tickers": {}}
        blocks.append(_format_expert_block(result, ticker))

    return '<div class="expert-grid">' + "\n".join(blocks) + "</div>"
