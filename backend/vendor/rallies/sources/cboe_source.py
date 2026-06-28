import logging
import re

import requests

from .registry import SourceResult

logger = logging.getLogger(__name__)

CBOE_QUOTE = "https://www.cboe.com/api/options/quote"
CBOE_VIX = "https://cdn.cboe.com/api/global/us_indices/definitions/historical_data"


class CBOESource:
    name = "cboe"

    @property
    def available(self):
        return True

    def query(self, tickers, context=""):
        return None

    def get_options_chain(self, ticker, max_items=10):
        try:
            resp = requests.get(
                f"{CBOE_QUOTE}/{ticker.upper()}",
                params={"strikeRange": "ATM"},
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            )
            if not resp.ok:
                return None
            data = resp.json()
            options = data.get("data", {})
            calls = (options.get("calls") or [])[:max_items]
            puts = (options.get("puts") or [])[:max_items]
            result = {"ticker": ticker.upper(), "calls": [], "puts": []}
            for opt in calls:
                result["calls"].append({
                    "strike": opt.get("strike", ""),
                    "expiration": opt.get("expiration", "")[:10],
                    "bid": opt.get("bid", ""),
                    "ask": opt.get("ask", ""),
                    "volume": opt.get("volume", 0),
                    "iv": opt.get("iv", ""),
                })
            for opt in puts:
                result["puts"].append({
                    "strike": opt.get("strike", ""),
                    "expiration": opt.get("expiration", "")[:10],
                    "bid": opt.get("bid", ""),
                    "ask": opt.get("ask", ""),
                    "volume": opt.get("volume", 0),
                    "iv": opt.get("iv", ""),
                })
            return SourceResult(self.name, result) if result["calls"] or result["puts"] else None
        except Exception as e:
            logger.debug("CBOE options chain failed: %s", e)
            return None

    def get_vix(self):
        # Fallback: use yfinance if available, otherwise try CBOE
        try:
            import yfinance as yf
            v = yf.Ticker("^VIX")
            info = v.info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
            high = info.get("regularMarketDayHigh") or info.get("dayHigh")
            low = info.get("regularMarketDayLow") or info.get("dayLow")
            if price:
                change_pct = ""
                if price and prev:
                    change_pct = f"{(float(price)/float(prev)-1)*100:+.2f}%"
                return SourceResult(self.name, {
                    "vix": float(price),
                    "change": float(price) - float(prev) if prev else "",
                    "change_pct": change_pct,
                    "high": float(high) if high else "",
                    "low": float(low) if low else "",
                })
        except Exception:
            pass

        # Try CBOE direct as fallback
        try:
            resp = requests.get(
                "https://cdn.cboe.com/api/global/us_indices/quotes/VIX",
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            )
            if resp.ok:
                data = resp.json()
                quote = data.get("data", {})
                return SourceResult(self.name, {
                    "vix": quote.get("currentPrice", quote.get("price", "")),
                    "change": quote.get("change", ""),
                    "change_pct": quote.get("changePercent", ""),
                    "high": quote.get("high", ""),
                    "low": quote.get("low", ""),
                })
        except Exception:
            pass
        return None
