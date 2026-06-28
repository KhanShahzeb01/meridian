import logging

import requests

from .registry import SourceResult

logger = logging.getLogger(__name__)

HFM_BASE = "https://data.financialresearch.gov/hf/v1"

MNEMONICS = [
    ("FPF-ALLQHF_LEVERAGERATIO_GAVWMEAN", "HF Leverage (avg)"),
    ("FPF-ALLQHF_GAV_SUM", "Gross Assets (total)"),
    ("FPF-ALLQHF_NAV_SUM", "Net Assets (total)"),
    ("FPF-ALLQHF_GNE_SUM", "Gross Notional Exposure"),
    ("FICC-SPONSORED_REPO_VOL", "Sponsored Repo Volume"),
]


class HedgeFundSource:
    name = "hedgefund"

    @property
    def available(self):
        return True

    def query(self, tickers, context=""):
        return self.get_snapshot()

    def get_snapshot(self):
        results = {}
        for mnemonic, label in MNEMONICS:
            try:
                resp = requests.get(
                    f"{HFM_BASE}/series/timeseries",
                    params={
                        "mnemonic": mnemonic,
                        "start_date": "2024-01-01",
                        "remove_nulls": "true",
                        "periodicity": "Q",
                    },
                    timeout=10,
                )
                if not resp.ok:
                    continue
                data = resp.json()
                if data and len(data) > 0:
                    latest = data[-1]
                    prev = data[-2] if len(data) > 1 else None
                    results[mnemonic] = {
                        "label": label,
                        "value": latest[1] if len(latest) > 1 else None,
                        "date": latest[0] if len(latest) > 0 else "",
                        "previous": prev[1] if prev and len(prev) > 1 else None,
                    }
            except Exception as e:
                logger.debug("HFM series %s failed: %s", mnemonic, e)
                continue
        return SourceResult(self.name, results)
