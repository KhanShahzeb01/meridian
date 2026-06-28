import yfinance as yf
import pandas as pd
import time
import random
from datetime import datetime, timedelta
from typing import Optional

# Demo data for when Yahoo Finance is rate-limited
DEMO_QUOTES = {
    "AAPL": {"name": "Apple Inc.", "price": 227.52, "pe_ratio": 35.2, "eps": 6.46, "market_cap": 3.45e12, "sector": "Technology", "beta": 1.24},
    "MSFT": {"name": "Microsoft Corporation", "price": 415.30, "pe_ratio": 34.8, "eps": 11.94, "market_cap": 3.09e12, "sector": "Technology", "beta": 0.91},
    "GOOGL": {"name": "Alphabet Inc.", "price": 175.80, "pe_ratio": 23.5, "eps": 7.48, "market_cap": 2.15e12, "sector": "Communication Services", "beta": 1.05},
    "AMZN": {"name": "Amazon.com Inc.", "price": 198.45, "pe_ratio": 42.1, "eps": 4.71, "market_cap": 2.07e12, "sector": "Consumer Cyclical", "beta": 1.18},
    "NVDA": {"name": "NVIDIA Corporation", "price": 128.75, "pe_ratio": 55.3, "eps": 2.33, "market_cap": 3.16e12, "sector": "Technology", "beta": 1.72},
    "META": {"name": "Meta Platforms Inc.", "price": 585.20, "pe_ratio": 26.4, "eps": 22.17, "market_cap": 1.48e12, "sector": "Communication Services", "beta": 1.28},
    "TSLA": {"name": "Tesla Inc.", "price": 248.90, "pe_ratio": 62.5, "eps": 3.98, "market_cap": 794e9, "sector": "Consumer Cyclical", "beta": 2.08},
    "JPM": {"name": "JPMorgan Chase & Co.", "price": 242.15, "pe_ratio": 11.8, "eps": 20.52, "market_cap": 678e9, "sector": "Financial Services", "beta": 1.12},
    "BRK-B": {"name": "Berkshire Hathaway Inc.", "price": 458.30, "pe_ratio": 9.2, "eps": 49.81, "market_cap": 987e9, "sector": "Financial Services", "beta": 0.85},
}


def _demo_quote(ticker: str) -> dict:
    t = ticker.upper()
    demo = DEMO_QUOTES.get(t, {})
    base_price = demo.get("price", 100 + random.uniform(-20, 20))
    change_pct = round(random.uniform(-3, 3), 2)
    change = round(base_price * change_pct / 100, 2)
    return {
        "ticker": t,
        "name": demo.get("name", t),
        "price": round(base_price, 2),
        "change": change,
        "change_pct": change_pct,
        "open": round(base_price - change * 0.3, 2),
        "high": round(base_price * 1.02, 2),
        "low": round(base_price * 0.98, 2),
        "volume": random.randint(10_000_000, 80_000_000),
        "market_cap": demo.get("market_cap"),
        "pe_ratio": demo.get("pe_ratio"),
        "eps": demo.get("eps"),
        "dividend_yield": round(random.uniform(0, 0.03), 4) if t in ("JPM", "AAPL") else None,
        "fifty_two_week_high": round(base_price * 1.25, 2),
        "fifty_two_week_low": round(base_price * 0.75, 2),
        "beta": demo.get("beta"),
        "sector": demo.get("sector", "Unknown"),
        "industry": None,
        "updated_at": datetime.now().isoformat(),
        "demo_mode": True,
    }


def _safe_info(stock: yf.Ticker) -> dict:
    try:
        return stock.info or {}
    except Exception:
        return {}


def _quote_from_history(ticker: str, stock: yf.Ticker) -> dict:
    hist = stock.history(period="5d")
    if hist.empty:
        raise ValueError(f"No data found for {ticker}")

    current_price = float(hist["Close"].iloc[-1])
    prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
    change = current_price - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0

    return {
        "ticker": ticker.upper(),
        "name": ticker.upper(),
        "price": round(current_price, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "open": round(float(hist["Open"].iloc[-1]), 2),
        "high": round(float(hist["High"].iloc[-1]), 2),
        "low": round(float(hist["Low"].iloc[-1]), 2),
        "volume": int(hist["Volume"].iloc[-1]),
        "market_cap": None,
        "pe_ratio": None,
        "eps": None,
        "dividend_yield": None,
        "fifty_two_week_high": round(float(hist["High"].max()), 2),
        "fifty_two_week_low": round(float(hist["Low"].min()), 2),
        "beta": None,
        "sector": None,
        "industry": None,
        "updated_at": datetime.now().isoformat(),
    }


def get_quote(ticker: str) -> dict:
    ticker = ticker.upper()
    stock = yf.Ticker(ticker)

    # Try fast_info first (lighter API call)
    try:
        fi = stock.fast_info
        current_price = getattr(fi, "last_price", None) or getattr(fi, "previous_close", 0)
        prev_close = getattr(fi, "previous_close", current_price) or current_price
        change = (current_price or 0) - (prev_close or 0)
        change_pct = (change / prev_close * 100) if prev_close else 0

        if current_price:
            info = _safe_info(stock)
            return {
                "ticker": ticker,
                "name": info.get("longName") or info.get("shortName") or ticker,
                "price": round(float(current_price), 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "open": info.get("open") or info.get("regularMarketOpen"),
                "high": info.get("dayHigh") or getattr(fi, "day_high", None),
                "low": info.get("dayLow") or getattr(fi, "day_low", None),
                "volume": info.get("volume") or getattr(fi, "last_volume", None),
                "market_cap": info.get("marketCap") or getattr(fi, "market_cap", None),
                "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
                "eps": info.get("trailingEps"),
                "dividend_yield": info.get("dividendYield"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh") or getattr(fi, "year_high", None),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow") or getattr(fi, "year_low", None),
                "beta": info.get("beta"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "updated_at": datetime.now().isoformat(),
            }
    except Exception:
        pass

    # Fallback to history-based quote, then demo data
    try:
        return _quote_from_history(ticker, stock)
    except Exception:
        return _demo_quote(ticker)


def get_financials(ticker: str) -> dict:
    stock = yf.Ticker(ticker.upper())
    info = _safe_info(stock)

    income = stock.financials
    balance = stock.balance_sheet
    cashflow = stock.cashflow

    def df_to_dict(df):
        if df is None or df.empty:
            return {}
        result = {}
        for col in df.columns[:4]:
            year = col.strftime("%Y") if hasattr(col, "strftime") else str(col)
            result[year] = {str(idx): float(val) if pd.notna(val) else None for idx, val in df[col].items()}
        return result

    return {
        "ticker": ticker.upper(),
        "name": info.get("longName", ticker.upper()),
        "income_statement": df_to_dict(income),
        "balance_sheet": df_to_dict(balance),
        "cash_flow": df_to_dict(cashflow),
        "key_metrics": {
            "revenue": info.get("totalRevenue"),
            "gross_profit": info.get("grossProfits"),
            "operating_income": info.get("operatingIncome"),
            "net_income": info.get("netIncomeToCommon"),
            "total_debt": info.get("totalDebt"),
            "total_cash": info.get("totalCash"),
            "free_cash_flow": info.get("freeCashflow"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
        },
    }


def get_news(ticker: str, limit: int = 10) -> list:
    stock = yf.Ticker(ticker.upper())
    news = stock.news or []
    return [
        {
            "title": item.get("title", ""),
            "publisher": item.get("publisher", ""),
            "link": item.get("link", ""),
            "published": datetime.fromtimestamp(item.get("providerPublishTime", 0)).isoformat()
            if item.get("providerPublishTime")
            else None,
            "type": item.get("type", "news"),
        }
        for item in news[:limit]
    ]


def get_filings(ticker: str) -> dict:
    stock = yf.Ticker(ticker.upper())
    try:
        filings = stock.sec_filings or []
        return {
            "ticker": ticker.upper(),
            "filings": [
                {
                    "type": f.get("type", ""),
                    "date": f.get("date", ""),
                    "title": f.get("title", ""),
                    "url": f.get("edgarUrl", ""),
                }
                for f in filings[:10]
            ],
        }
    except Exception:
        return {"ticker": ticker.upper(), "filings": [], "note": "SEC filings data unavailable"}


def get_dcf_data(ticker: str) -> dict:
    stock = yf.Ticker(ticker.upper())
    info = _safe_info(stock)
    cashflow = stock.cashflow

    fcf_history = []
    if cashflow is not None and not cashflow.empty and "Free Cash Flow" in cashflow.index:
        for col in cashflow.columns[:5]:
            year = col.strftime("%Y") if hasattr(col, "strftime") else str(col)
            val = cashflow.loc["Free Cash Flow", col]
            if pd.notna(val):
                fcf_history.append({"year": year, "fcf": float(val)})

    return {
        "ticker": ticker.upper(),
        "name": info.get("longName", ticker.upper()),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "fcf_history": fcf_history,
        "free_cash_flow": info.get("freeCashflow"),
        "operating_cash_flow": info.get("operatingCashflow"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "beta": info.get("beta", 1.0),
        "market_cap": info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
        "pe_ratio": info.get("trailingPE"),
        "peg_ratio": info.get("pegRatio"),
        "analyst_target": info.get("targetMeanPrice"),
        "recommendation": info.get("recommendationKey"),
    }


def get_batch_quotes(tickers: list[str]) -> list[dict]:
    results = []
    for ticker in tickers:
        try:
            results.append(get_quote(ticker))
        except Exception as e:
            results.append({"ticker": ticker.upper(), "error": str(e)})
    return results


def screen_stocks(
    sector: Optional[str] = None,
    min_market_cap: Optional[float] = None,
    max_pe: Optional[float] = None,
    min_dividend_yield: Optional[float] = None,
) -> list[dict]:
    """Basic screener using predefined popular tickers as universe."""
    universe = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
        "JPM", "V", "UNH", "JNJ", "WMT", "PG", "MA", "HD", "DIS", "BAC",
        "XOM", "CVX", "PFE", "KO", "PEP", "COST", "ABBV", "MRK", "TMO",
        "AVGO", "LLY", "CSCO", "ACN", "MCD", "ABT", "DHR", "NEE", "TXN",
        "NKE", "PM", "ORCL", "CRM", "AMD", "INTC", "QCOM", "IBM", "GS",
    ]

    results = []
    for i, ticker in enumerate(universe):
        try:
            if i > 0:
                time.sleep(0.3)
            q = get_quote(ticker)
            if sector and q.get("sector", "").lower() != sector.lower():
                continue
            if min_market_cap and (q.get("market_cap") or 0) < min_market_cap:
                continue
            if max_pe and q.get("pe_ratio") and q["pe_ratio"] > max_pe:
                continue
            if min_dividend_yield and (q.get("dividend_yield") or 0) < min_dividend_yield:
                continue
            results.append(q)
        except Exception:
            continue
    return results
