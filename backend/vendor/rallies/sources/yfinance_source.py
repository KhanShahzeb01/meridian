import json
import logging

from .registry import SourceResult

logger = logging.getLogger(__name__)


def _import_yfinance():
    try:
        import yfinance as yf
        import logging as _yl
        # Prevent noisy HTTP errors from yfinance internals from polluting CLI output.
        _yl.getLogger("yfinance").setLevel(_yl.CRITICAL)
        return yf
    except ImportError:
        return None


from ..yfinance_metrics import info_snapshot, quote_dict


class YFinanceSource:
    name = "yfinance"

    @property
    def available(self):
        return _import_yfinance() is not None

    def query(self, tickers, context=""):
        yf = _import_yfinance()
        if yf is None:
            return None
        try:
            ticker = yf.Ticker(tickers[0])
            info = ticker.info or {}
            fast_info = ticker.fast_info
            price = {}
            try:
                price["current_price"] = fast_info.last_price
                price["previous_close"] = fast_info.previous_close
                price["day_high"] = fast_info.day_high
                price["day_low"] = fast_info.day_low
                price["volume"] = fast_info.last_volume
                price["change"] = fast_info.last_price - fast_info.previous_close if fast_info.last_price and fast_info.previous_close else None
                price["change_pct"] = (price["change"] / fast_info.previous_close * 100) if price.get("change") and fast_info.previous_close else None
            except Exception:
                price["current_price"] = info.get("currentPrice") or info.get("regularMarketPrice")
                price["previous_close"] = info.get("previousClose") or info.get("regularMarketPreviousClose")
                price["day_high"] = info.get("dayHigh") or info.get("regularMarketDayHigh")
                price["day_low"] = info.get("dayLow") or info.get("regularMarketDayLow")
                price["volume"] = info.get("volume") or info.get("regularMarketVolume")

            snap = info_snapshot(info)
            summary = {
                "ticker": tickers[0],
                "company_name": snap.get("name") or tickers[0],
                "price": price,
                "market_cap": snap.get("market_cap"),
                "pe_ratio": snap.get("pe_trailing") if snap.get("pe_trailing") is not None else snap.get("pe_forward"),
                "pe_forward": snap.get("pe_forward"),
                "peg_5yr": snap.get("peg_5yr"),
                "eps_trailing": snap.get("eps_trailing"),
                "dividend_yield": snap.get("dividend_yield_pct"),
                "sector": snap.get("sector"),
                "industry": snap.get("industry"),
                "52w_high": snap.get("fifty_two_week_high"),
                "52w_low": snap.get("fifty_two_week_low"),
                "avg_volume": info.get("averageVolume"),
            }
            return SourceResult(self.name, summary)
        except Exception as e:
            logger.warning("yfinance query failed for %s: %s", tickers[0], e)
            return SourceResult(self.name, None, error=str(e))

    def get_quote(self, ticker):
        yf = _import_yfinance()
        if yf is None:
            return None
        try:
            t = yf.Ticker(ticker)
            return quote_dict(ticker, t.info or {})
        except Exception as e:
            return {"ticker": ticker.upper(), "error": str(e)}

    _FN_ROWS = [
        ("Total Revenue", "Total Revenue"),
        ("Cost Of Revenue", "Cost of Revenue"),
        ("Gross Profit", "Gross Profit"),
        ("Operating Expense", "Operating Expense"),
        ("Operating Income", "Operating Income"),
        ("Net Income", "Net Income"),
        ("EBITDA", "EBITDA"),
        ("Earnings Per Share", ("dilutedEPS", "basicEPS")),
        ("Gross Margin", None),
        ("Operating Margin", None),
        ("Net Margin", None),
    ]

    def get_financials(self, ticker, years=4):
        yf = _import_yfinance()
        if yf is None:
            return None
        try:
            t = yf.Ticker(ticker)
            fs = t.financials
            if fs is None or fs.empty:
                return {"ticker": ticker.upper(), "error": "No financial data available"}
            cols = fs.columns[:years]
            result = {"ticker": ticker.upper(), "periods": [str(c.date()) for c in cols], "rows": []}
            for label, keys in self._FN_ROWS:
                if keys is None:
                    continue
                row = {"label": label}
                if isinstance(keys, str):
                    keys = (keys,)
                vals = []
                for col in cols:
                    val = None
                    for k in keys:
                        if k in fs.index:
                            v = fs.loc[k, col]
                            if v is not None and v == v:
                                val = float(v)
                                break
                    vals.append(val)
                row["values"] = vals
                result["rows"].append(row)

            info = t.info or {}
            shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
            if shares:
                shares = float(shares)
                for i, r in enumerate(result["rows"]):
                    if r["label"] == "Net Income" and r["values"]:
                        eps_row = None
                        for rr in result["rows"]:
                            if rr["label"] == "Earnings Per Share":
                                eps_row = rr
                                break
                        if eps_row:
                            for j, v in enumerate(r["values"]):
                                if v is not None and j < len(eps_row["values"]) and eps_row["values"][j] is None:
                                    eps_row["values"][j] = round(v / shares, 2)
            return result
        except Exception as e:
            return {"ticker": ticker.upper(), "error": str(e)}
