"""Fast /memo for Meridian web — one LLM call, no 3-expert panel, minimal data fetch."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

from services.bootstrap import meridian_home
from services.command_format import format_quote_markdown
from services.fast_llm import fast_prompt

FAST_MEMO_SYSTEM = """You are a buyside analyst writing a concise investment memo in markdown.
Use ONLY numbers from the live data block. Never invent prices, dates, or financials.
If data is missing, say unavailable.

Structure (use these headings):
## Executive summary
## Investment thesis (3-5 bullets)
## Valuation & price target ({horizon} horizon, {direction})
## Key risks
## Catalysts to watch

Keep the memo under 400 words. Be direct. Cite actual figures from the data."""


def _parse_memo_args(prompt: str) -> tuple[str, str, str] | None:
    parts = prompt.strip().split()
    if len(parts) < 3 or not parts[0].lower().startswith("/memo"):
        return None
    if parts[1].lower() in ("--full", "-f"):
        return None
    ticker = parts[1].upper().lstrip("$")
    direction = parts[2].lower()
    if direction not in ("long", "short", "l", "s"):
        return None
    horizon = parts[3] if len(parts) > 3 else "12mo"
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,5}", ticker):
        return None
    direction_label = "LONG" if direction.startswith("l") else "SHORT"
    return ticker, direction_label, horizon


def _fetch_bundle_short(registry: Any, ticker: str, timeout: float = 12.0) -> str:
    from rallies.research.skills.actions import gather_equity_bundle

    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(gather_equity_bundle, registry, ticker)
        try:
            return (fut.result(timeout=timeout) or "")[:6000]
        except Exception as exc:
            return f"(Bundle fetch skipped: {exc})"


def _fetch_news_short(ticker: str) -> str:
    import os
    import requests

    key = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not key:
        return ""
    try:
        from datetime import datetime, timedelta

        to_d = datetime.now().strftime("%Y-%m-%d")
        from_d = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        resp = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker, "from": from_d, "to": to_d, "token": key},
            timeout=6,
        )
        if not resp.ok:
            return ""
        lines = ["## Recent headlines"]
        for art in (resp.json() or [])[:4]:
            headline = (art.get("headline") or "")[:100]
            if headline:
                lines.append(f"- {headline}")
        return "\n".join(lines) if len(lines) > 1 else ""
    except Exception:
        return ""


def _save_memo_markdown(ticker: str, direction: str, body: str) -> str:
    memos_dir = meridian_home() / "memos"
    memos_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    path = memos_dir / f"{ticker}_{direction}_{stamp}_fast.md"
    path.write_text(body, encoding="utf-8")
    return str(path)


def run_fast_memo(prompt: str, manager: Any, console: Any) -> str:
    parsed = _parse_memo_args(prompt)
    if not parsed:
        raise ValueError("Invalid /memo usage")

    ticker, direction, horizon = parsed
    llm = getattr(getattr(manager, "agent", None), "llm", None)
    if llm is None:
        raise RuntimeError("LLM unavailable")

    registry = getattr(manager, "data_registry", None)
    console.print(
        f"\n[bold magenta]Fast memo[/bold magenta] — "
        f"[white]{ticker}[/white] [dim]{direction} · {horizon}[/dim]\n"
    )
    console.print("[yellow]Step 1/2[/yellow] Live quote & headlines…")

    yfs = registry.get_source("yfinance") if registry else None
    quote = yfs.get_quote(ticker) if yfs else None
    if not quote or quote.get("error"):
        from services.market_data import finnhub_quote_dict

        quote = finnhub_quote_dict(ticker) or {"ticker": ticker, "error": "no quote"}

    data_parts = [format_quote_markdown(quote)]
    news = _fetch_news_short(ticker)
    if news:
        data_parts.append(news)

    data_block = "\n\n".join(p for p in data_parts if p.strip())
    console.print("[yellow]Step 2/2[/yellow] Drafting memo (single pass)…")

    system = FAST_MEMO_SYSTEM.format(horizon=horizon, direction=direction)
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"Ticker: {ticker}\nDirection: {direction}\nHorizon: {horizon}\n\n"
                f"## Live data\n{data_block[:12_000]}\n\n"
                "Write the investment memo in markdown."
            ),
        },
    ]
    memo_body = fast_prompt(llm, messages, task_type="summary")
    if not memo_body:
        raise RuntimeError("Model returned an empty memo")

    header = f"# {ticker} — {direction} memo ({horizon})\n\n"
    full_doc = header + memo_body
    path = _save_memo_markdown(ticker, direction, full_doc)

    return (
        f"{memo_body}\n\n---\n\n"
        f"*Fast memo saved to* `{path}`\n\n"
        f"*Tip: use* `/memo --full {ticker} long {horizon}` *for full HTML memo with expert panel (slower).*"
    )
