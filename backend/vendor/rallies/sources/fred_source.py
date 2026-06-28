import logging
import os

import requests

from .registry import SourceResult

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"

SERIES_MAP = {
    "FEDFUNDS": "Fed Funds Rate",
    "CPIAUCSL": "CPI (All Urban)",
    "UNRATE": "Unemployment Rate",
    "GDP": "GDP (Nominal)",
    "GDPC1": "GDP (Real)",
    "DGS10": "10-Year Treasury",
    "DGS2": "2-Year Treasury",
    "T10Y2Y": "10Y-2Y Spread",
    "SP500": "S&P 500",
    "UMCSENT": "Consumer Sentiment",
    "M2SL": "M2 Money Supply",
    "INDPRO": "Industrial Production",
}


class FREDSource:
    name = "fred"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    @property
    def available(self):
        return bool(self.api_key)

    def query(self, tickers, context=""):
        if not self.available:
            return None
        return self.get_snapshot()

    def get_snapshot(self, series_ids=None):
        if not self.available:
            return {"error": "FRED_API_KEY not set"}
        if series_ids is None:
            series_ids = list(SERIES_MAP.keys())
        results = {}
        for sid in series_ids:
            try:
                resp = requests.get(
                    f"{FRED_BASE}/series/observations",
                    params={
                        "api_key": self.api_key,
                        "series_id": sid,
                        "sort_order": "desc",
                        "limit": 2,
                        "file_type": "json",
                    },
                    timeout=10,
                )
                if not resp.ok:
                    continue
                data = resp.json()
                obs = data.get("observations", [])
                if len(obs) >= 1:
                    latest = obs[0]
                    val = latest.get("value")
                    prev = obs[1].get("value") if len(obs) > 1 else None
                    if val and val != ".":
                        results[sid] = {
                            "label": SERIES_MAP.get(sid, sid),
                            "value": float(val),
                            "date": latest.get("date", ""),
                            "previous": float(prev) if prev and prev != "." else None,
                        }
            except Exception as e:
                logger.debug("FRED series %s failed: %s", sid, e)
                continue
        return SourceResult(self.name, results)

    def get_macro_summary(self):
        data = self.get_snapshot()
        if data is None or isinstance(data, dict) and "error" in data:
            return data
        return data.data if isinstance(data, SourceResult) else data
