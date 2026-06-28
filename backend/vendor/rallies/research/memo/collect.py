"""Deterministic data collection for investment memos."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoDataPack:
    ticker: str
    bundle: str = ""
    mda: str = ""
    dcf: str = ""
    web: str = ""
    valuation_facts: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _fetch_bundle(registry: Any, ticker: str) -> str:
    from ..skills.actions import gather_equity_bundle

    return gather_equity_bundle(registry, ticker)


def _fetch_mda(ticker: str) -> str:
    from ..filing.section_fetch import fetch_filing_section, format_filing_section

    result = fetch_filing_section(ticker, "MD&A")
    return format_filing_section(result)


def _fetch_dcf(ticker: str) -> str:
    from ..skills.actions import run_dcf_quant

    return run_dcf_quant(ticker)


def _fetch_optional_web(ticker: str) -> str:
    """Best-effort IR / company site fetch when yfinance exposes a URL."""
    try:
        import yfinance as yf

        from ..web import fetch_url

        info = yf.Ticker(ticker).info or {}
        website = (info.get("website") or "").strip()
        if not website:
            return ""
        if not website.startswith("http"):
            website = f"https://{website}"
        payload = fetch_url(website)
        title = payload.get("title") or website
        body = (payload.get("markdown") or "")[:12_000]
        return f"## Web — {title}\n\n{body}"
    except Exception as e:
        return f"(Web fetch skipped: {e})"


def _fetch_valuation_facts(ticker: str) -> dict:
    try:
        from rallies.charts.data import build_pe_frame
        from rallies.charts.facts import build_valuation_facts
        from rallies.charts.horizons import horizon_for_key

        series = build_pe_frame(ticker.upper(), horizon_for_key("5y"))
        return build_valuation_facts(series)
    except Exception as exc:
        return {"error": str(exc)}


def collect_memo_data(
    registry: Any,
    ticker: str,
    *,
    include_web: bool = True,
    console: Any | None = None,
) -> MemoDataPack:
    pack = MemoDataPack(ticker=ticker.upper())
    tasks: dict[str, Any] = {
        "bundle": lambda: _fetch_bundle(registry, ticker),
        "mda": lambda: _fetch_mda(ticker),
        "dcf": lambda: _fetch_dcf(ticker),
        "valuation": lambda: _fetch_valuation_facts(ticker),
    }
    if include_web:
        tasks["web"] = lambda: _fetch_optional_web(ticker)

    def _emit(msg: str) -> None:
        if console is not None:
            console.print(f"[bright_black]{msg}[/bright_black]")

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): key for key, fn in tasks.items()}
        for fut in as_completed(futures):
            key = futures[fut]
            _emit(f"Memo data · {key}…")
            try:
                text = fut.result() or ""
            except Exception as e:
                pack.errors.append(f"{key}: {e}")
                text = ""
            if key == "bundle":
                pack.bundle = text
            elif key == "mda":
                pack.mda = text
            elif key == "dcf":
                pack.dcf = text
            elif key == "valuation":
                pack.valuation_facts = text if isinstance(text, dict) else {}
            elif key == "web":
                pack.web = text

    return pack


def pack_to_context_text(pack: MemoDataPack) -> str:
    blocks = [
        f"# Memo data — {pack.ticker}",
        pack.bundle,
        pack.mda,
        pack.dcf,
    ]
    if pack.valuation_facts and not pack.valuation_facts.get("error"):
        from rallies.charts.facts import format_facts_for_llm

        blocks.append(
            "## Valuation facts (trailing, from /chart engine)\n"
            + format_facts_for_llm(pack.valuation_facts)
        )
    if pack.web:
        blocks.append(pack.web)
    if pack.errors:
        blocks.append("## Collection notes\n" + "\n".join(f"- {e}" for e in pack.errors))
    return "\n\n".join(b for b in blocks if b and b.strip())
