"""Dollar and quantity conventions for research / compound prompts."""

from __future__ import annotations

import re

DOLLAR_UNIT_RULES = """## Dollar and quantity units (mandatory)
- Portfolio **quantities are shares** (may be fractional, e.g. 0.4 or 1.15). Do not multiply by 1,000 unless the user wrote a suffix.
- Bare dollar numbers are **literal USD**: $491.44 is four hundred ninety-one dollars, not $491 thousand.
- Suffixes mean scale only when written: **k** / **K** / thousand → ×1,000; **mn** / **MM** / million → ×1,000,000; **bn** / **B** / billion → ×1,000,000,000 (e.g. $100k = $100,000).
- **Market cap** on a quote is the **company** size (often billions). **Position value** = shares × share price (retail lots are usually hundreds–low thousands USD).
- Rebalancing math: use position value = qty × price; portfolio total = sum of position values. Example: ~$7,620 total, not ~$7.6M, when line items are ~$200–$700 each."""


def format_usd_literal(amount: float) -> str:
    """Unambiguous USD for agent context (avoids silent 'k' scaling)."""
    a = float(amount)
    if abs(a) >= 1_000_000:
        return f"${a:,.2f} ({a / 1e6:.2f} mn)"
    return f"${a:,.2f} USD"


def parse_dollar_amount(text: str) -> float | None:
    """
    Parse a dollar amount with optional k/mn/bn suffix.
    No suffix → literal value (100 → 100.0, not 100_000).
    """
    raw = str(text).strip().replace(",", "").replace("$", "").strip()
    if not raw:
        return None
    m = re.fullmatch(
        r"([+-]?\d+(?:\.\d+)?)\s*(k|K|thousand|mn|MM|million|bn|B|billion)?",
        raw,
        re.IGNORECASE,
    )
    if not m:
        return None
    value = float(m.group(1))
    suffix = (m.group(2) or "").lower()
    if suffix in ("k", "thousand"):
        value *= 1_000
    elif suffix in ("mn", "mm", "million"):
        value *= 1_000_000
    elif suffix in ("bn", "b", "billion"):
        value *= 1_000_000_000
    return value
