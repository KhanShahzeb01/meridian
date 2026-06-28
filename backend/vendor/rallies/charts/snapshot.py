"""Point-in-time valuation snapshot from yfinance (Yahoo key statistics parity)."""

from __future__ import annotations

from ..yfinance_metrics import info_snapshot


def build_market_snapshot(info: dict) -> dict | None:
    """
    Fields aligned with Yahoo Finance key statistics and stocks_valuation notebook.
    """
    if not info:
        return None

    snap = info_snapshot(info)
    if not snap:
        return None

    out: dict = {}
    mapping = {
        "price": "price",
        "eps_trailing": "eps_trailing",
        "pe_trailing": "pe_trailing",
        "forward_pe": "pe_forward",
        "forward_eps": "eps_forward",
        "peg_trailing": "peg_5yr",
        "ev_to_ebitda": "ev_to_ebitda",
        "target_mean": "target_mean",
        "target_high": "target_high",
        "target_low": "target_low",
        "sector": "sector",
        "industry": "industry",
        "growth_5yr_expected_pct": "growth_5yr_expected_pct",
        "target_upside_pct": "target_upside_pct",
        "forward_pe_below_trailing": "forward_pe_below_trailing",
        "forward_pe_discount_pct": "forward_pe_discount_pct",
    }
    for out_key, snap_key in mapping.items():
        v = snap.get(snap_key)
        if v is not None and v != "":
            out[out_key] = v

    feps = out.get("forward_eps")
    price = out.get("price")
    if price and feps and feps > 0:
        out["implied_forward_pe_from_eps"] = round(price / feps, 2)
    elif out.get("forward_pe") is not None:
        out["implied_forward_pe_from_eps"] = round(float(out["forward_pe"]), 2)

    return out or None


def fetch_market_snapshot(ticker: str) -> dict | None:
    from .data import _import_yf

    yf = _import_yf()
    if yf is None:
        return None
    info = yf.Ticker(ticker.upper()).info or {}
    return build_market_snapshot(info)
