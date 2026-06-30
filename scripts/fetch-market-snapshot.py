#!/usr/bin/env python3
"""Fetch indices, headlines, and quotes for static GitHub Pages (bypasses browser CORS)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from services.market_dashboard import (  # noqa: E402
    TAPE_SYMBOLS,
    _fetch_yahoo_chart,
    get_indices_dashboard,
    get_yahoo_headlines,
)

# Popular tickers for /quote on GitHub Pages (snapshot fallback when CORS blocks live fetch)
QUOTE_SYMBOLS = tuple(
    dict.fromkeys(
        [
            *TAPE_SYMBOLS,
            "NVDA",
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "META",
            "TSLA",
            "SPY",
            "QQQ",
            "AMD",
            "NFLX",
            "COIN",
            "PLTR",
            "BRK-B",
        ]
    )
)


def fetch_quotes() -> dict[str, dict]:
    quotes: dict[str, dict] = {}
    for sym in QUOTE_SYMBOLS:
        _series, quote = _fetch_yahoo_chart(sym)
        if not quote or quote.get("price") is None:
            continue
        price = float(quote["price"])
        prev = quote.get("prev_close")
        change_pct = None
        if prev not in (None, 0):
            change_pct = (price - float(prev)) / float(prev) * 100
        quotes[sym.upper()] = {
            "price": price,
            "prev_close": prev,
            "change_pct": change_pct,
        }
    return quotes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        default=str(ROOT / "frontend" / "public" / "market-snapshot.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    indices = get_indices_dashboard()
    headlines = get_yahoo_headlines(25)
    quotes = fetch_quotes()
    payload = {
        "indices": indices.get("indices", []),
        "headlines": headlines.get("headlines", []),
        "quotes": quotes,
        "updated_at": headlines.get("updated_at") or indices.get("updated_at"),
        "source": "yahoo_finance",
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {out} ({len(payload['indices'])} indices, "
        f"{len(payload['headlines'])} headlines, {len(quotes)} quotes)"
    )


if __name__ == "__main__":
    main()
