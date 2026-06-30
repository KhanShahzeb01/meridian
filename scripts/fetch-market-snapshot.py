#!/usr/bin/env python3
"""Fetch indices + headlines for static GitHub Pages (bypasses browser CORS)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from services.market_dashboard import get_indices_dashboard, get_yahoo_headlines  # noqa: E402


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
    payload = {
        "indices": indices.get("indices", []),
        "headlines": headlines.get("headlines", []),
        "updated_at": headlines.get("updated_at") or indices.get("updated_at"),
        "source": "yahoo_finance",
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(payload['indices'])} indices, {len(payload['headlines'])} headlines)")


if __name__ == "__main__":
    main()
