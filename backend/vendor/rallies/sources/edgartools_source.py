import logging
import re

from .edgar_filing_text import extract_filing_description
from .registry import SourceResult

logger = logging.getLogger(__name__)


def _import_edgar():
    try:
        from edgar import Company, set_identity
        identity = "Rallies CLI (research@rallies.ai)"
        try:
            set_identity(identity)
        except Exception:
            pass
        return Company
    except ImportError:
        return None


class EdgarToolsSource:
    name = "edgartools"

    _extract_filing_description = staticmethod(extract_filing_description)

    @staticmethod
    def _to_float_safe(value, default=0.0):
        """Parse numbers that may include annotations (e.g. '0 [F1]')."""
        if value in (None, ""):
            return float(default)
        if isinstance(value, (int, float)):
            try:
                return float(value)
            except Exception:
                return float(default)

        text = str(value).strip().replace(",", "")
        # Match first numeric token, allowing sign and exponent forms.
        match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
        if match:
            try:
                return float(match.group(0))
            except Exception:
                return float(default)
        return float(default)

    @property
    def available(self):
        return _import_edgar() is not None

    def query(self, tickers, context=""):
        Company = _import_edgar()
        if Company is None:
            return None
        try:
            company = Company(tickers[0])
            filings = company.get_filings(form="8-K").latest(3)
            data = {"ticker": tickers[0], "filings": []}
            for filing in filings:
                data["filings"].append({
                    "form": filing.form,
                    "date": filing.filing_date,
                    "description": filing.description or "",
                })
            return SourceResult(self.name, data)
        except Exception as e:
            logger.warning("edgartools query failed for %s: %s", tickers[0], e)
            return SourceResult(self.name, None, error=str(e))

    def get_recent_filings(self, ticker, form="8-K", count=5):
        Company = _import_edgar()
        if Company is None:
            return None
        try:
            company = Company(ticker)
            filings = company.get_filings(form=form).latest(count)
            return [
                {
                    "form": f.form,
                    "date": f.filing_date,
                    "description": self._extract_filing_description(f),
                }
                for f in filings
            ]
        except Exception as e:
            return {"error": str(e)}

    def get_insider_trades(self, ticker, count=10):
        Company = _import_edgar()
        if Company is None:
            return None
        try:
            company = Company(ticker)
            filings_obj = company.get_filings(form="4")
            if filings_obj is None:
                return [{"info": "No insider filing data available"}]
            filings = filings_obj.latest(count)
            if filings is None:
                return [{"info": "No recent insider filings"}]
            trades = []
            for f in filings:
                obj = f.obj()
                if obj is None:
                    continue
                activities = obj.get_transaction_activities()
                if not activities:
                    continue
                for act in activities[:3]:
                    owner_name = getattr(act, "display_name", "")
                    ttype = getattr(act, "transaction_type", "")
                    shares = getattr(act, "shares_numeric", 0) or getattr(act, "shares", 0)
                    price = getattr(act, "price_numeric", 0) or getattr(act, "price_per_share", 0)
                    sec_title = getattr(act, "security_title", "")
                    is_plan = getattr(act, "is_10b5_1_plan", False)
                    trades.append({
                        "date": f.filing_date,
                        "owner": str(owner_name)[:40] if owner_name else "",
                        "type": str(ttype) if ttype else "",
                        "shares": self._to_float_safe(shares, default=0.0),
                        "price": self._to_float_safe(price, default=0.0) if price not in (None, "") else "",
                        "security": str(sec_title)[:30] if sec_title else "",
                        "plan": is_plan,
                    })
            if not trades:
                return [{"info": "No insider trades found in recent filings"}]
            return trades[:count]
        except Exception as e:
            return [{"error": str(e)}]

    def get_institutional_holdings(self, ticker, count=10):
        Company = _import_edgar()
        if Company is None:
            return None
        try:
            company = Company(ticker)
            filings_obj = company.get_filings(form="13F-HR")
            if filings_obj is None:
                return [{"info": "No 13F filings available for this ticker"}]
            filing = filings_obj.latest(1)
            if filing is None:
                return [{"info": "No recent 13F filing found"}]
            # Handle single EntityFiling vs iterable
            if hasattr(filing, "obj"):
                filing = [filing]
            holdings = []
            for f in filing:
                obj = f.obj()
                if obj is None:
                    continue
                infotable = getattr(obj, "infotable", None)
                if infotable is None:
                    continue
                if hasattr(infotable, "to_dict"):
                    rows = infotable.to_dict()
                    if isinstance(rows, dict):
                        rows = [rows]
                    for entry in rows[:count]:
                        holdings.append({
                            "issuer": entry.get("nameOfIssuer", ""),
                            "ticker": entry.get("ticker", ""),
                            "value": entry.get("value", entry.get("fair_value", 0)),
                            "shares": entry.get("shares", entry.get("ssh_prnamt", entry.get("shares_numeric", 0))),
                            "type": entry.get("type", entry.get("put_call", "")),
                        })
                elif hasattr(infotable, "to_dataframe"):
                    df = infotable.to_dataframe()
                    if df is not None and not df.empty:
                        for _, row in df.head(count).iterrows():
                            holdings.append({
                                "issuer": row.get("nameOfIssuer", row.get("issuer", "")),
                                "ticker": row.get("ticker", ""),
                                "value": row.get("value", row.get("fair_value", 0)),
                                "shares": row.get("shares", row.get("ssh_prnamt", 0)),
                                "type": row.get("type", ""),
                            })
                elif isinstance(infotable, list):
                    for entry in infotable[:count]:
                        if isinstance(entry, dict):
                            holdings.append({
                                "issuer": entry.get("nameOfIssuer", entry.get("issuer", "")),
                                "ticker": entry.get("ticker", ""),
                                "value": entry.get("value", entry.get("fair_value", 0)),
                                "shares": entry.get("shares", entry.get("ssh_prnamt", 0)),
                                "type": entry.get("type", ""),
                            })
            return holdings if holdings else [{"info": "No holdings data in latest filing"}]
        except Exception as e:
            return [{"error": str(e)}]
