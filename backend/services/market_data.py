"""Reliable market data with Finnhub/FRED fallbacks when Yahoo Finance is rate-limited."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"
FRED_BASE = "https://api.stlouisfed.org/fred"

_CACHE: dict[str, tuple[float, Any]] = {}
_QUOTE_TTL = 45
_FINANCIALS_TTL = 600
_VIX_TTL = 300


def _cache_get(key: str, ttl: float) -> Any | None:
    hit = _CACHE.get(key)
    if not hit:
        return None
    ts, val = hit
    if time.time() - ts > ttl:
        return None
    return val


def _cache_set(key: str, val: Any) -> Any:
    _CACHE[key] = (time.time(), val)
    return val


def _finnhub_key() -> str:
    return os.environ.get("FINNHUB_API_KEY", "").strip()


def _fred_key() -> str:
    return os.environ.get("FRED_API_KEY", "").strip()


def _finnhub_get(path: str, params: dict | None = None) -> Any | None:
    key = _finnhub_key()
    if not key:
        return None
    params = dict(params or {})
    params["token"] = key
    try:
        resp = requests.get(f"{FINNHUB_BASE}/{path}", params=params, timeout=8)
        if not resp.ok:
            return None
        return resp.json()
    except Exception as exc:
        logger.debug("Finnhub %s failed: %s", path, exc)
        return None


def finnhub_quote_dict(ticker: str) -> dict[str, Any] | None:
    """Return a quote dict compatible with rallies `quote_dict` shape."""
    sym = ticker.upper().lstrip("$")
    cache_key = f"quote:{sym}"
    cached = _cache_get(cache_key, _QUOTE_TTL)
    if cached:
        return cached

    quote = _finnhub_get("quote", {"symbol": sym})
    if not quote or not quote.get("c"):
        return None

    profile = _finnhub_get("stock/profile2", {"symbol": sym}) or {}
    metrics = (_finnhub_get("stock/metric", {"symbol": sym, "metric": "all"}) or {}).get(
        "metric", {}
    ) or {}

    market_cap = profile.get("marketCapitalization")
    if isinstance(market_cap, (int, float)):
        market_cap = float(market_cap) * 1_000_000  # Finnhub reports millions USD

    pe = metrics.get("peTTM") or metrics.get("peNormalizedAnnual")
    eps = metrics.get("epsAnnual")
    div_yield = metrics.get("dividendYieldIndicatedAnnual")
    if isinstance(div_yield, (int, float)):
        # Finnhub returns yield already in percent (e.g. 0.39 = 0.39%).
        div_yield = float(div_yield) if div_yield < 15 else div_yield

    as_of = ""
    ts = quote.get("t")
    if isinstance(ts, (int, float)) and ts > 0:
        as_of = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    data = {
        "ticker": sym,
        "name": profile.get("name") or sym,
        "price": float(quote["c"]),
        "prev_close": float(quote.get("pc")) if quote.get("pc") is not None else None,
        "change_pct": float(quote.get("dp")) if quote.get("dp") is not None else None,
        "day_high": float(quote.get("h")) if quote.get("h") is not None else None,
        "day_low": float(quote.get("l")) if quote.get("l") is not None else None,
        "volume": None,
        "market_cap": market_cap,
        "pe": float(pe) if pe is not None else None,
        "pe_forward": None,
        "eps": float(eps) if eps is not None else None,
        "peg_5yr": None,
        "dividend_yield_pct": float(div_yield) if div_yield is not None else None,
        "sector": profile.get("finnhubIndustry") or "",
        "industry": profile.get("finnhubIndustry") or "",
        "source": "finnhub",
        "as_of": as_of,
    }
    return _cache_set(cache_key, data)


def finnhub_financials_dict(ticker: str, years: int = 4) -> dict[str, Any] | None:
    sym = ticker.upper().lstrip("$")
    cache_key = f"financials:{sym}:{years}"
    cached = _cache_get(cache_key, _FINANCIALS_TTL)
    if cached:
        return cached

    payload = _finnhub_get("stock/financials-reported", {"symbol": sym})
    if not payload or not payload.get("data"):
        return None

    annual = [r for r in payload["data"] if str(r.get("form", "")).upper() == "10-K"]
    annual.sort(key=lambda r: int(r.get("year") or 0), reverse=True)
    annual = annual[:years]
    if not annual:
        return None

    periods: list[str] = []
    revenue_vals: list[float | None] = []
    net_vals: list[float | None] = []
    ebitda_vals: list[float | None] = []
    eps_vals: list[float | None] = []

    def _find_value(rows: list[dict], labels: tuple[str, ...]) -> float | None:
        for row in rows:
            label = str(row.get("label") or "").lower()
            for target in labels:
                if target in label:
                    val = row.get("value")
                    if isinstance(val, (int, float)):
                        return float(val)
        return None

    for report in annual:
        periods.append(str(report.get("year") or ""))
        rep = report.get("report") or {}
        ic = rep.get("ic") or []
        revenue_vals.append(_find_value(ic, ("net sales", "total revenue", "revenue")))
        net_vals.append(_find_value(ic, ("net income",)))
        ebitda_vals.append(_find_value(ic, ("ebitda",)))
        eps_vals.append(_find_value(ic, ("earnings per share", "eps")))

    rows = [
        {"label": "Total Revenue", "values": revenue_vals},
        {"label": "Net Income", "values": net_vals},
        {"label": "EBITDA", "values": ebitda_vals},
        {"label": "Earnings Per Share", "values": eps_vals},
    ]

    result = {
        "ticker": sym,
        "periods": periods,
        "rows": rows,
        "source": "finnhub",
    }
    return _cache_set(cache_key, result)


def fred_vix_dict() -> dict[str, Any] | None:
    cache_key = "vix:fred"
    cached = _cache_get(cache_key, _VIX_TTL)
    if cached:
        return cached

    key = _fred_key()
    if not key:
        return None
    try:
        resp = requests.get(
            f"{FRED_BASE}/series/observations",
            params={
                "api_key": key,
                "series_id": "VIXCLS",
                "sort_order": "desc",
                "limit": 2,
                "file_type": "json",
            },
            timeout=8,
        )
        if not resp.ok:
            return None
        obs = resp.json().get("observations") or []
        if not obs:
            return None
        latest = obs[0]
        prev = obs[1] if len(obs) > 1 else None
        val = latest.get("value")
        if not val or val == ".":
            return None
        vix = float(val)
        prev_v = float(prev["value"]) if prev and prev.get("value") not in (None, ".") else None
        change = vix - prev_v if prev_v is not None else None
        change_pct = f"{(change / prev_v * 100):+.2f}%" if change is not None and prev_v else ""
        data = {
            "vix": vix,
            "change": change if change is not None else "",
            "change_pct": change_pct,
            "high": "",
            "low": "",
            "date": latest.get("date", ""),
            "source": "fred",
        }
        return _cache_set(cache_key, data)
    except Exception as exc:
        logger.debug("FRED VIX failed: %s", exc)
        return None


def patch_data_sources() -> None:
    """Monkey-patch vendored sources to use reliable fallbacks."""
    from rallies.sources.yfinance_source import YFinanceSource
    from rallies.sources.cboe_source import CBOESource
    from rallies.agent.agent import Agent
    from rallies.sources.registry import SourceResult

    if getattr(YFinanceSource, "_meridian_patched", False):
        return

    _orig_get_quote = YFinanceSource.get_quote
    _orig_get_financials = YFinanceSource.get_financials

    def _get_quote(self, ticker):  # noqa: ANN001
        fallback = finnhub_quote_dict(ticker)
        if fallback:
            return fallback
        data = _orig_get_quote(self, ticker)
        if data and "error" not in data and data.get("price") is not None:
            data["source"] = "yfinance"
            return data
        return data or fallback

    def _get_financials(self, ticker, years=4):  # noqa: ANN001
        fallback = finnhub_financials_dict(ticker, years=years)
        if fallback:
            return fallback
        data = _orig_get_financials(self, ticker, years=years)
        if data and "error" not in data and data.get("rows"):
            data["source"] = "yfinance"
            return data
        return data or fallback

    YFinanceSource.get_quote = _get_quote  # type: ignore[method-assign]
    YFinanceSource.get_financials = _get_financials  # type: ignore[method-assign]
    YFinanceSource._meridian_patched = True  # type: ignore[attr-defined]

    _orig_get_vix = CBOESource.get_vix

    def _get_vix(self):  # noqa: ANN001
        fred = fred_vix_dict()
        if fred:
            return SourceResult("fred", fred)
        return _orig_get_vix(self)

    CBOESource.get_vix = _get_vix  # type: ignore[method-assign]

    _orig_prefetch = Agent.build_compare_prefetch

    def _build_compare_prefetch(self, tickers, *, max_tickers=5):  # noqa: ANN001
        block = _orig_prefetch(self, tickers, max_tickers=max_tickers)
        if block and "quote unavailable" not in block.lower():
            return block
        if not self.data_registry or not tickers:
            return block or ""
        yfs = self.data_registry.get_source("yfinance")
        if not yfs:
            return block or ""
        from rallies.quotes import format_yfinance_quote_line

        lines = [
            "## Prefetched live market data (all tickers in user question)",
            "Use these exact figures. Do not ask the user to fetch more data.",
            "If a figure is missing, say data is unavailable — never invent prices.",
        ]
        use = tickers if max_tickers is None else tickers[:max_tickers]
        for ticker in use:
            data = yfs.get_quote(ticker)
            lines.append(format_yfinance_quote_line(data or {"ticker": ticker, "error": True}))
        rebuilt = "\n".join(lines)
        return rebuilt if "Price $" in rebuilt else (block or rebuilt)

    Agent.build_compare_prefetch = _build_compare_prefetch  # type: ignore[method-assign]
