"""Normalize yfinance `info` fields for consistent units (Yahoo Finance parity)."""

from __future__ import annotations


def _f(info: dict, *keys: str) -> float | None:
    for k in keys:
        v = info.get(k)
        if v is None:
            continue
        try:
            fv = float(v)
            if fv == fv:
                return fv
        except (TypeError, ValueError):
            continue
    return None


def _price(info: dict) -> float | None:
    return _f(info, "currentPrice", "regularMarketPrice")


def _prev_close(info: dict) -> float | None:
    return _f(info, "previousClose", "regularMarketPreviousClose")


def dividend_yield_percent(info: dict) -> float | None:
    """
    Dividend yield in percent (e.g. 0.96 for ~1%).

    yfinance `dividendYield` is inconsistent: sometimes decimal (0.0096),
    sometimes already percent (0.96). Prefer dividendRate / price when available.
    """
    if not info:
        return None
    rate = _f(info, "dividendRate")
    price = _price(info)
    if rate is not None and price and price > 0:
        return rate / price * 100.0

    dy = _f(info, "dividendYield")
    if dy is None:
        return None
    if dy <= 0.2:
        return dy * 100.0
    return dy


def trailing_pe(info: dict) -> float | None:
    """Trailing P/E from info; never fall through to forward on zero/negative."""
    v = info.get("trailingPE") if info else None
    if v is None:
        return None
    try:
        fv = float(v)
        return fv if fv == fv else None
    except (TypeError, ValueError):
        return None


def forward_pe(info: dict) -> float | None:
    v = info.get("forwardPE") if info else None
    if v is None:
        return None
    try:
        fv = float(v)
        return fv if fv == fv else None
    except (TypeError, ValueError):
        return None


def peg_ratio_5yr(info: dict) -> float | None:
    return _f(info, "trailingPegRatio", "pegRatio")


def trailing_eps(info: dict) -> float | None:
    return _f(info, "trailingEps")


def forward_eps(info: dict) -> float | None:
    return _f(info, "forwardEps")


def surprise_percent(value: float | None) -> float | None:
    """
    yfinance `surprisePercent` is usually a ratio (0.047 → 4.7% beat).
    Values with abs >= 1 are treated as already percent (e.g. 3.3 → 3.3%).
    """
    if value is None:
        return None
    try:
        v = float(value)
        if v != v:
            return None
    except (TypeError, ValueError):
        return None
    if abs(v) < 1.0:
        return v * 100.0
    return v


def growth_rate_percent(info: dict, *keys: str) -> float | None:
    """
    yfinance growth/margin/ROE fields are decimals (0.133 → 13.3%).
    Values with abs > 2 are treated as already percent.
    """
    v = _f(info, *keys) if info else None
    if v is None:
        return None
    if abs(v) <= 2.0:
        return v * 100.0
    return v


def change_pct(info: dict) -> float | None:
    price = _price(info)
    prev = _prev_close(info)
    if price is None or prev is None or prev == 0:
        return None
    return (price / prev - 1.0) * 100.0


def mom_3m_percent(ticker) -> float | None:
    """
    Total return over ~3 months using adjusted closes (percent, e.g. 12.5 = +12.5%).
    """
    try:
        hist = ticker.history(period="3mo", auto_adjust=True)
        if hist is None or hist.empty or len(hist) < 10:
            return None
        start = float(hist["Close"].iloc[0])
        end = float(hist["Close"].iloc[-1])
        if start <= 0:
            return None
        return (end / start - 1.0) * 100.0
    except Exception:
        return None


def info_snapshot(info: dict | None) -> dict:
    """
    Normalized Yahoo key statistics for CLI / quote / watchlist / peers.

    Percent fields end with `_pct`. Raw yfinance decimals kept as `_decimal` for screener scoring.
    """
    if not info:
        return {}

    price = _price(info)
    t_pe = trailing_pe(info)
    peg5 = peg_ratio_5yr(info)
    out: dict = {
        "price": price,
        "prev_close": _prev_close(info),
        "change_pct": change_pct(info),
        "pe_trailing": t_pe,
        "pe_forward": forward_pe(info),
        "eps_trailing": trailing_eps(info),
        "eps_forward": forward_eps(info),
        "peg_5yr": peg5,
        "dividend_yield_pct": dividend_yield_percent(info),
        "revenue_growth_pct": growth_rate_percent(info, "revenueGrowth"),
        "earnings_growth_pct": growth_rate_percent(info, "earningsGrowth"),
        "profit_margin_pct": growth_rate_percent(info, "profitMargins"),
        "roe_pct": growth_rate_percent(info, "returnOnEquity"),
        "roa_pct": growth_rate_percent(info, "returnOnAssets"),
        "pb": _f(info, "priceToBook"),
        "ps": _f(info, "priceToSalesTrailing12Months"),
        "ev_to_ebitda": _f(info, "enterpriseToEbitda"),
        "market_cap": info.get("marketCap"),
        "sector": info.get("sector") or "",
        "industry": info.get("industry") or "",
        "name": info.get("longName") or info.get("shortName") or "",
        "target_mean": _f(info, "targetMeanPrice"),
        "target_low": _f(info, "targetLowPrice"),
        "target_high": _f(info, "targetHighPrice"),
        "fifty_two_week_low": _f(info, "fiftyTwoWeekLow"),
        "fifty_two_week_high": _f(info, "fiftyTwoWeekHigh"),
        "day_high": _f(info, "dayHigh", "regularMarketDayHigh"),
        "day_low": _f(info, "dayLow", "regularMarketDayLow"),
        "volume": info.get("volume") or info.get("regularMarketVolume"),
        "recommendation": info.get("recommendationKey") or "",
        "analyst_count": info.get("numberOfAnalystOpinions"),
        # Raw decimals for screener scoring (orchestrator multiplies by 100)
        "revenue_growth_decimal": _f(info, "revenueGrowth"),
        "earnings_growth_decimal": _f(info, "earningsGrowth"),
        "profit_margin_decimal": _f(info, "profitMargins"),
        "roe_decimal": _f(info, "returnOnEquity"),
        "roa_decimal": _f(info, "returnOnAssets"),
    }
    if peg5 and peg5 > 0 and t_pe:
        out["growth_5yr_expected_pct"] = round(t_pe / peg5, 1)
    if price and out.get("target_mean"):
        out["target_upside_pct"] = round((out["target_mean"] - price) / price * 100, 1)
    if t_pe and out.get("pe_forward") is not None:
        f_pe = out["pe_forward"]
        out["forward_pe_below_trailing"] = f_pe < t_pe
        if t_pe:
            out["forward_pe_discount_pct"] = round((1 - f_pe / t_pe) * 100, 1)
    return out


def quote_dict(ticker: str, info: dict | None) -> dict:
    """Shape used by yfinance_source.get_quote and /quote /sector."""
    snap = info_snapshot(info or {})
    return {
        "ticker": ticker.upper(),
        "name": snap.get("name") or "",
        "price": snap.get("price"),
        "prev_close": snap.get("prev_close"),
        "change_pct": snap.get("change_pct"),
        "day_high": snap.get("day_high"),
        "day_low": snap.get("day_low"),
        "volume": snap.get("volume"),
        "market_cap": snap.get("market_cap"),
        "pe": snap.get("pe_trailing"),
        "pe_forward": snap.get("pe_forward"),
        "eps": snap.get("eps_trailing"),
        "peg_5yr": snap.get("peg_5yr"),
        "dividend_yield_pct": snap.get("dividend_yield_pct"),
        "sector": snap.get("sector"),
        "industry": snap.get("industry"),
    }
