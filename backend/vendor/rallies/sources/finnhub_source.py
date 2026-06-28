import logging
import os

import requests

from .registry import SourceResult

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"

_EARNINGS_CACHE = {}
_PEERS_CACHE = {}


class FinnhubSource:
    name = "finnhub"

    def __init__(self):
        self.api_key = os.environ.get("FINNHUB_API_KEY", "")

    @property
    def available(self):
        return bool(self.api_key)

    def query(self, tickers, context=""):
        return None

    def _get(self, path, params=None):
        if not self.available:
            return None
        params = dict(params or {})
        params["token"] = self.api_key
        try:
            resp = requests.get(f"{FINNHUB_BASE}/{path}", params=params, timeout=10)
            if not resp.ok:
                return None
            return resp.json()
        except Exception as e:
            logger.debug("Finnhub %s failed: %s", path, e)
            return None

    def get_company_news(self, ticker, max_items=5):
        from datetime import datetime, timedelta
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        data = self._get("company-news", {
            "symbol": ticker.upper(),
            "from": from_date,
            "to": to_date,
        })
        if not data or not isinstance(data, list):
            return None
        news = data[:max_items]
        result = {
            "ticker": ticker.upper(),
            "headlines": [],
        }
        for art in news:
            dt = art.get("datetime", "")
            if isinstance(dt, (int, float)):
                dt = datetime.fromtimestamp(dt).strftime("%m-%d") if dt else ""
            else:
                dt = str(dt)[:10]
            result["headlines"].append({
                "headline": (art.get("headline", "") or "")[:120],
                "source": art.get("source", ""),
                "date": dt,
                "url": art.get("url", ""),
                "summary": (art.get("summary", "") or "")[:150],
            })
        return SourceResult(self.name, result)

    def get_earnings_calendar(self, from_date=None, to_date=None, max_items=10):
        cache_key = f"{from_date}_{to_date}"
        if cache_key in _EARNINGS_CACHE:
            return _EARNINGS_CACHE[cache_key]
        from datetime import datetime, timedelta
        if not from_date:
            from_date = datetime.now().strftime("%Y-%m-%d")
        if not to_date:
            to_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        data = self._get("calendar/earnings", {"from": from_date, "to": to_date})
        if not data:
            return None
        earnings = (data.get("earningsCalendar") or [])[:max_items]
        result = []
        for e in earnings:
            result.append({
                "date": e.get("date", ""),
                "ticker": e.get("symbol", ""),
                "quarter": e.get("quarter", 0),
                "year": e.get("year", 0),
                "estimate": e.get("epsEstimate", "") or "",
                "revenue_est": e.get("revenueEstimate", "") or "",
                "hour": e.get("hour", ""),
            })
        _EARNINGS_CACHE[cache_key] = result
        return SourceResult(self.name, {"earnings": result})

    def get_recommendation_trends(self, ticker):
        data = self._get("stock/recommendation", {"symbol": ticker.upper()})
        if not data:
            return None
        if isinstance(data, list):
            data = data[:3]
        result = {"ticker": ticker.upper(), "trends": []}
        if isinstance(data, list):
            for entry in data:
                result["trends"].append({
                    "period": entry.get("period", ""),
                    "buy": entry.get("buy", 0),
                    "hold": entry.get("hold", 0),
                    "sell": entry.get("sell", 0),
                    "strong_buy": entry.get("strongBuy", 0),
                    "strong_sell": entry.get("strongSell", 0),
                })
        return SourceResult(self.name, result)

    def get_peers(self, ticker):
        data = self._get("stock/peers", {"symbol": ticker.upper()})
        if not data or not isinstance(data, list):
            return None
        return SourceResult(self.name, {"ticker": ticker.upper(), "peers": data[:15]})
