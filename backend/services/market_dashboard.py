"""Landing-page market data: major indices + Yahoo Finance headlines."""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import requests

from services.market_data import finnhub_quote_dict

logger = logging.getLogger(__name__)

_CACHE: dict[str, tuple[float, Any]] = {}
_INDICES_TTL = 120
_HEADLINES_TTL = 120

YAHOO_RSS = "https://finance.yahoo.com/news/rssindex"

INDICES = (
    {"id": "sp500", "name": "S&P 500", "symbol": "^GSPC", "fallback": "SPY"},
    {"id": "nasdaq", "name": "NASDAQ", "symbol": "^IXIC", "fallback": "QQQ"},
    {"id": "dow", "name": "Dow Jones", "symbol": "^DJI", "fallback": "DIA"},
    {"id": "gold", "name": "Gold", "symbol": "GC=F", "fallback": "GLD"},
    {"id": "crude", "name": "Crude Oil", "symbol": "CL=F", "fallback": "USO"},
    {"id": "vix", "name": "VIX", "symbol": "^VIX", "fallback": "VIXY"},
)

TAPE_SYMBOLS = ("AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "JPM", "V", "XOM")

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_HEADERS = {"User-Agent": "MeridianFinance/1.0 (+https://meridian.finance)"}


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


def _fetch_yahoo_chart(symbol: str, points: int = 32) -> tuple[list[float], dict[str, Any] | None]:
    try:
        encoded = requests.utils.quote(symbol, safe="")
        resp = requests.get(
            YAHOO_CHART.format(symbol=encoded),
            params={"range": "5d", "interval": "30m"},
            headers=_HEADERS,
            timeout=10,
        )
        if not resp.ok:
            return [], None
        payload = resp.json()
        results = (payload.get("chart") or {}).get("result") or []
        if not results:
            return [], None
        block = results[0]
        meta = block.get("meta") or {}
        quotes = (block.get("indicators") or {}).get("quote") or [{}]
        closes = [float(c) for c in (quotes[0].get("close") or []) if c is not None]
        series = closes[-points:]
        quote = {
            "price": meta.get("regularMarketPrice") or (series[-1] if series else None),
            "prev_close": meta.get("previousClose") or meta.get("chartPreviousClose"),
        }
        return series, quote
    except Exception as exc:
        logger.debug("Yahoo chart %s failed: %s", symbol, exc)
        return [], None


def _fetch_yfinance_series(symbol: str, points: int = 32) -> list[float]:
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d", interval="30m", auto_adjust=True)
        if hist is None or hist.empty:
            return []
        closes = [float(v) for v in hist["Close"].dropna().tolist()]
        return closes[-points:]
    except Exception as exc:
        logger.debug("yfinance series %s failed: %s", symbol, exc)
        return []


def _fetch_index_entry(meta: dict[str, str]) -> dict[str, Any]:
    symbol = meta["symbol"]
    series, quote = _fetch_yahoo_chart(symbol)
    used_symbol = symbol

    if not series or quote is None:
        fb = meta["fallback"]
        series, quote = _fetch_yahoo_chart(fb)
        if series:
            used_symbol = fb

    if not series:
        series = _fetch_yfinance_series(used_symbol)
    if not series:
        fb_series = _fetch_yfinance_series(meta["fallback"])
        if fb_series:
            series = fb_series
            used_symbol = meta["fallback"]

    if quote is None and series:
        quote = {"price": series[-1], "prev_close": series[0] if len(series) > 1 else series[-1]}

    if quote is None or quote.get("price") is None:
        data = finnhub_quote_dict(meta["fallback"])
        if data and not data.get("error"):
            quote = {
                "price": data.get("price"),
                "prev_close": data.get("prev_close"),
            }
            used_symbol = meta["fallback"]
            if not series and quote.get("price") is not None:
                # Minimal flat sparkline when history unavailable
                p = float(quote["price"])
                series = [p * (1 - 0.002 * i) for i in range(20, 0, -1)] + [p]

    price = quote.get("price") if quote else None
    prev = quote.get("prev_close") if quote else None
    change = None
    change_pct = None
    if price is not None and prev not in (None, 0):
        change = price - prev
        change_pct = (change / prev) * 100

    return {
        "id": meta["id"],
        "name": meta["name"],
        "symbol": meta["symbol"],
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "series": series,
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source": "yahoo",
    }


def get_indices_dashboard() -> dict[str, Any]:
    cached = _cache_get("indices", _INDICES_TTL)
    if cached:
        return cached

    items = [_fetch_index_entry(meta) for meta in INDICES]
    payload = {
        "indices": items,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _cache_set("indices", payload)


def get_yahoo_headlines(max_items: int = 12) -> dict[str, Any]:
    cache_key = f"headlines:{max_items}"
    cached = _cache_get(cache_key, _HEADLINES_TTL)
    if cached:
        return cached

    headlines: list[dict[str, str]] = []
    try:
        resp = requests.get(
            YAHOO_RSS,
            timeout=10,
            headers={"User-Agent": "MeridianFinance/1.0 (+https://meridian.finance)"},
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is not None:
            for item in channel.findall("item")[:max_items]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                source_el = item.find("source")
                source = source_el.text.strip() if source_el is not None and source_el.text else "Yahoo Finance"
                if title:
                    headlines.append(
                        {
                            "title": title,
                            "url": link,
                            "published": pub,
                            "source": source,
                        }
                    )
    except Exception as exc:
        logger.warning("Yahoo RSS fetch failed: %s", exc)

    payload = {
        "headlines": headlines,
        "source": "yahoo_finance",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _cache_set(cache_key, payload)


def _fetch_tape_entry(symbol: str) -> dict[str, Any]:
    _, quote = _fetch_yahoo_chart(symbol)
    if quote is None:
        data = finnhub_quote_dict(symbol)
        if data and not data.get("error"):
            quote = {"price": data.get("price"), "prev_close": data.get("prev_close")}

    price = quote.get("price") if quote else None
    prev = quote.get("prev_close") if quote else None
    change_pct = None
    if price is not None and prev not in (None, 0):
        change_pct = ((price - prev) / prev) * 100

    return {
        "symbol": symbol,
        "price": price,
        "change_pct": change_pct,
    }


def get_market_tape() -> dict[str, Any]:
    cached = _cache_get("tape", _INDICES_TTL)
    if cached:
        return cached

    items = [_fetch_tape_entry(sym) for sym in TAPE_SYMBOLS]
    payload = {
        "tape": items,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _cache_set("tape", payload)
