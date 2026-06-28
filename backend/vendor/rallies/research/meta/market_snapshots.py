"""Macro and hedge-fund snapshots for /research (no ticker required)."""

from __future__ import annotations

from typing import Any


def macro_snapshot(registry: Any) -> str:
    """FRED macro summary — same data as /macro."""
    fred = registry.get_source("fred") if registry else None
    if fred is None or not getattr(fred, "available", False):
        return (
            "FRED macro unavailable. Set FRED_API_KEY (free at "
            "https://fred.stlouisfed.org/docs/api/api_key.html) or run /macro."
        )
    result = fred.get_macro_summary()
    data = result.data if hasattr(result, "data") else result
    lines = ["## Macro snapshot (FRED)"]
    for sid in ("FEDFUNDS", "CPIAUCSL", "UNRATE", "DGS10", "GDPC1"):
        entry = (data or {}).get(sid)
        if entry:
            lines.append(
                f"- {entry.get('label', sid)}: {entry.get('value')} "
                f"({entry.get('date', 'n/a')})"
            )
    return "\n".join(lines) if len(lines) > 1 else "FRED returned no macro series."


def hedgefund_snapshot(registry: Any) -> str:
    """OFR Hedge Fund Monitor — same data as /hedgefund."""
    hf = registry.get_source("hedgefund") if registry else None
    if hf is None:
        return "Hedge Fund Monitor source unavailable."
    result = hf.get_snapshot()
    data = result.data if hasattr(result, "data") else result
    if not data:
        return "No hedge fund monitor data returned."
    lines = ["## Hedge fund industry snapshot (OFR)"]
    for mnemonic, entry in data.items():
        if not isinstance(entry, dict):
            continue
        label = entry.get("label", mnemonic)
        val = entry.get("value")
        date = entry.get("date", "")
        prev = entry.get("previous")
        if isinstance(val, float):
            if "REPO" in mnemonic:
                val_s = f"${val:,.0f}"
            elif val > 1e9:
                val_s = f"${val:,.0f}"
            else:
                val_s = f"{val:.4f}"
        else:
            val_s = str(val)
        line = f"- {label}: {val_s} ({date})"
        if prev is not None:
            line += f" [prior: {prev}]"
        lines.append(line)
    return "\n".join(lines)
