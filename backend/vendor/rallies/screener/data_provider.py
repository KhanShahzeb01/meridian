import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..storage import Storage

logger = logging.getLogger(__name__)

BASIC_CACHE_TTL = 3600
DEEP_CACHE_TTL = 7200


def _import_yf():
    try:
        import yfinance as yf
        import logging as _yl
        _yl.getLogger("yfinance").setLevel(_yl.CRITICAL)
        return yf
    except ImportError:
        return None


BasicMetrics = dict[str, dict[str, float | str | None]]
DeepMetrics = dict[str, dict[str, float | str | None]]


def _get_basic(ticker: str) -> dict | None:
    yf = _import_yf()
    if yf is None:
        return None
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        mcap = info.get("marketCap")
        from ..yfinance_metrics import info_snapshot

        snap = info_snapshot(info)
        return {
            "price": snap.get("price") or price,
            "mcap": snap.get("market_cap") or mcap,
            "pe": snap.get("pe_trailing"),
            "sector": snap.get("sector") or "",
            "industry": snap.get("industry") or "",
            "name": snap.get("name") or ticker,
        }
    except Exception:
        return None


def fetch_basic(tickers: list[str], storage: Storage | None = None) -> BasicMetrics:
    results: dict[str, dict] = {}

    cached_keys: dict[str, str] = {}
    if storage:
        for t in tickers:
            cached = storage.cache_get(f"screen:basic:{t}")
            if cached is not None and isinstance(cached, dict):
                results[t] = cached
            else:
                cached_keys[t] = f"screen:basic:{t}"

    if cached_keys:
        yf = _import_yf()
        if yf is None:
            return results

        with ThreadPoolExecutor(max_workers=10) as ex:
            remaining = list(cached_keys.keys())
            futures = {ex.submit(_get_basic, t): t for t in remaining}
            for f in as_completed(futures):
                t = futures[f]
                try:
                    data = f.result()
                    if data and data.get("price") is not None:
                        results[t] = data
                        if storage:
                            key = cached_keys[t]
                            storage.cache_set(key, data, ttl_seconds=BASIC_CACHE_TTL)
                except Exception:
                    pass

    return results


def _get_deep(ticker: str) -> dict | None:
    yf = _import_yf()
    if yf is None:
        return None
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        mcap = info.get("marketCap")
        from ..yfinance_metrics import info_snapshot

        snap = info_snapshot(info)
        trailing_pe = snap.get("pe_trailing")
        forward_pe = snap.get("pe_forward")
        pb = snap.get("pb")
        ps = snap.get("ps")
        peg = snap.get("peg_5yr")
        sector = snap.get("sector")
        industry = snap.get("industry")
        name = snap.get("name") or ticker
        div_yield = snap.get("dividend_yield_pct")
        roe = snap.get("roe_decimal")
        roa = snap.get("roa_decimal")
        de = info.get("debtToEquity")
        rev_growth = snap.get("revenue_growth_decimal")
        earnings_growth = snap.get("earnings_growth_decimal")
        gross_margin = info.get("grossMargins")
        op_margin = info.get("operatingMargins")
        profit_margin = snap.get("profit_margin_decimal")
        beta = info.get("beta")
        rec_key = info.get("recommendationKey")
        target_mean = info.get("targetMeanPrice")
        target_high = info.get("targetHighPrice")
        target_low = info.get("targetLowPrice")
        fifty_two_high = info.get("fiftyTwoWeekHigh")
        fifty_two_low = info.get("fiftyTwoWeekLow")
        avg_vol = info.get("averageVolume")
        volume = info.get("volume") or info.get("regularMarketVolume")
        shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
        free_cf = info.get("freeCashflow")
        payout = info.get("payoutRatio")

        change_pct = snap.get("change_pct")
        if change_pct is None and price and prev_close:
            change_pct = (float(price) / float(prev_close) - 1) * 100

        from ..yfinance_metrics import mom_3m_percent

        mom_3m_pct = mom_3m_percent(t)
        eps = snap.get("eps_trailing")

        return {
            "ticker": ticker, "name": name, "price": price,
            "prev_close": prev_close, "change_pct": change_pct,
            "mom_3m_pct": mom_3m_pct,
            "mcap": mcap, "sector": sector or "", "industry": industry or "",
            "pe": trailing_pe, "forward_pe": forward_pe, "pb": pb, "ps": ps, "peg": peg,
            "div_yield": div_yield, "payout": payout,
            "eps": eps, "roe": roe, "roa": roa, "de": de,
            "rev_growth": rev_growth, "earnings_growth": earnings_growth,
            "gross_margin": gross_margin, "op_margin": op_margin, "profit_margin": profit_margin,
            "beta": beta, "free_cf": free_cf,
            "rec_key": rec_key, "target_mean": target_mean,
            "target_high": target_high, "target_low": target_low,
            "fifty_two_high": fifty_two_high, "fifty_two_low": fifty_two_low,
            "avg_vol": avg_vol, "volume": volume, "shares": shares,
        }
    except Exception:
        return None


def fetch_deep(tickers: list[str], storage: Storage | None = None) -> DeepMetrics:
    results: dict[str, dict] = {}

    cached_keys: dict[str, str] = {}
    if storage:
        for t in tickers:
            cached = storage.cache_get(f"screen:deep:{t}")
            if cached is not None and isinstance(cached, dict):
                results[t] = cached
            else:
                cached_keys[t] = f"screen:deep:{t}"
    else:
        cached_keys = {t: f"screen:deep:{t}" for t in tickers}

    if cached_keys:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(_get_deep, t): t for t in cached_keys}
            for f in as_completed(futures):
                t = futures[f]
                try:
                    data = f.result()
                    if data and data.get("price") is not None:
                        results[t] = data
                        if storage:
                            storage.cache_set(cached_keys[t], data, ttl_seconds=DEEP_CACHE_TTL)
                except Exception:
                    pass

    return results
