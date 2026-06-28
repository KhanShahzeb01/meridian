import logging
from datetime import datetime, timedelta

import requests

from .registry import SourceResult

logger = logging.getLogger(__name__)

SEC_SEARCH = "https://efts.sec.gov/LATEST/search-index"


class SECSource:
    name = "sec"

    @property
    def available(self):
        return True

    def query(self, tickers, context=""):
        return None

    def search_filings(self, query, max_items=8):
        try:
            payload = {
                "q": query,
                "dateRange": "custom",
                "startdt": (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d"),
                "enddt": datetime.now().strftime("%Y-%m-%d"),
                "from": 0,
                "size": max_items,
            }
            resp = requests.post(
                SEC_SEARCH,
                json=payload,
                timeout=15,
                headers={
                    "User-Agent": "Rallies CLI (research@rallies.ai)",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            if not resp.ok:
                return None
            data = resp.json()
            hits = (data.get("hits", {}).get("hits", {}).get("hits", [])
                    if isinstance(data, dict) else [])
            results = []
            for hit in hits[:max_items]:
                src = hit.get("_source", hit)
                results.append({
                    "ticker": src.get("ticker", ""),
                    "form": src.get("form", ""),
                    "date": (src.get("file_date", "") or src.get("period_ending", ""))[:10],
                    "description": (src.get("description", "") or src.get("display_names", [""])[0])[:150],
                    "url": _format_sec_url(src),
                })
            return SourceResult(self.name, {"query": query, "results": results})
        except Exception as e:
            logger.debug("SEC search failed: %s", e)
            return None

    def search_ticker_events(self, ticker, keywords="", max_items=5):
        q = f'"{ticker.upper()}"'
        if keywords:
            q += f" AND ({keywords})"
        return self.search_filings(q, max_items=max_items)


def _format_sec_url(src):
    try:
        cik = src.get("cik", "")
        accession = src.get("accession_number", "")
        if cik and accession:
            return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{accession}"
    except Exception:
        pass
    return ""
