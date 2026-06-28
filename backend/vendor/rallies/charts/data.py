"""Build P/E and PEG time series from yfinance."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from .horizons import Horizon

logger = logging.getLogger(__name__)


@dataclass
class MetricSeries:
    ticker: str
    metric: str  # pe | peg | valuation
    horizon: Horizon
    frame: pd.DataFrame  # date index: price, eps_ttm, pe, peg, eps_growth_yoy, ...
    company_name: str
    market: dict | None = None  # point-in-time yfinance snapshot (not plotted on trailing series)

    @property
    def forward(self) -> dict | None:
        return _legacy_forward_from_market(self.market)


def _legacy_forward_from_market(market: dict | None) -> dict | None:
    """Backward-compatible forward-only dict for older callers."""
    if not market:
        return None
    out = {}
    if market.get("forward_pe") is not None:
        out["forward_pe"] = market["forward_pe"]
    if market.get("forward_eps") is not None:
        out["forward_eps"] = market["forward_eps"]
    return out or None


def add_valuation_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Peter Lynch-style fair-value bands: price implied by EPS × historical P/E percentiles.
    Also rolling ~5y EPS CAGR for scatter (smoother than noisy YoY).
    """
    out = df.copy()
    pe = out["pe"].dropna()
    if not pe.empty:
        p25, p75, med = float(pe.quantile(0.25)), float(pe.quantile(0.75)), float(pe.median())
        eps = out["eps_ttm"]
        out["price_fair_low"] = eps * p25
        out["price_fair_high"] = eps * p75
        out["price_fair_median"] = eps * med

    if len(out) >= 252 and "eps_ttm" in out.columns:
        years = min(5.0, len(out) / 252.0)
        shift = max(1, int(years * 252))
        prior = out["eps_ttm"].shift(shift)
        ratio = out["eps_ttm"] / prior.replace(0, pd.NA)
        out["eps_growth_5y_cagr"] = (ratio ** (1.0 / years) - 1.0) * 100.0

    return out


def _import_yf():
    try:
        import yfinance as yf
        import logging as _yl

        _yl.getLogger("yfinance").setLevel(_yl.CRITICAL)
        return yf
    except ImportError:
        return None


def _quarterly_eps_series_from_stmt(stmt) -> pd.Series:
    if stmt is None or stmt.empty:
        return pd.Series(dtype=float)
    row = None
    for label in ("Diluted EPS", "Basic EPS", "Earnings Per Share"):
        if label in stmt.index:
            row = stmt.loc[label]
            break
    if row is None:
        return pd.Series(dtype=float)
    s = pd.Series(row, dtype=float)
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    s = s.replace([float("inf"), float("-inf")], pd.NA).dropna()
    return s


def _eps_from_earnings_dates(ticker) -> pd.Series:
    """Reported quarterly EPS from earnings calendar (often deeper than income_stmt columns)."""
    ed = getattr(ticker, "earnings_dates", None)
    if ed is None or getattr(ed, "empty", True):
        return pd.Series(dtype=float)
    if "Reported EPS" not in ed.columns:
        return pd.Series(dtype=float)
    s = ed["Reported EPS"].dropna().astype(float)
    idx = pd.to_datetime(s.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    s.index = idx
    return s.sort_index()


def _eps_from_earnings_history(ticker) -> pd.Series:
    hist = getattr(ticker, "earnings_history", None)
    if hist is None or getattr(hist, "empty", True):
        return pd.Series(dtype=float)
    if "epsActual" not in hist.columns:
        return pd.Series(dtype=float)
    s = hist["epsActual"].dropna().astype(float)
    idx = pd.to_datetime(s.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    s.index = idx
    return s.sort_index()


def _annual_eps_series(ticker) -> pd.Series:
    """Fiscal-year diluted EPS for longer horizons when quarterly TTM is sparse."""
    for attr in ("income_stmt", "financials"):
        candidate = getattr(ticker, attr, None)
        if candidate is not None and not getattr(candidate, "empty", True):
            s = _quarterly_eps_series_from_stmt(candidate)
            if not s.empty:
                return s
    return pd.Series(dtype=float)


def _quarterly_eps_series(ticker) -> pd.Series:
    """
    Quarterly diluted EPS for trailing P/E (Yahoo Finance parity).

    Use GAAP diluted EPS from quarterly income statements only. Do not merge
    ``earnings_history.epsActual`` — it often disagrees with statement EPS and
    inflates TTM (e.g. CRM ~15 vs Yahoo trailingEps ~8.6).
    """
    parts: list[pd.Series] = []
    for attr in ("quarterly_income_stmt", "quarterly_financials"):
        candidate = getattr(ticker, attr, None)
        if candidate is not None and not getattr(candidate, "empty", True):
            s = _quarterly_eps_series_from_stmt(candidate)
            if not s.empty:
                parts.append(s)

    if parts:
        combined = pd.concat(parts)
        combined = combined[~combined.index.duplicated(keep="last")]
        return combined.sort_index()

    ed = _eps_from_earnings_dates(ticker)
    if not ed.empty:
        return ed

    return _eps_from_earnings_history(ticker)


def _ttm_eps(quarterly: pd.Series) -> pd.Series:
    if quarterly.empty:
        return quarterly
    return quarterly.sort_index().rolling(4, min_periods=4).sum()


def _eps_for_merge(quarterly: pd.Series, annual: pd.Series) -> pd.Series:
    """
    Prefer trailing-four-quarter EPS; backfill older dates with last fiscal-year EPS
    so 5y/10y charts are not clipped to the latest few quarters only.
    """
    ttm = _ttm_eps(quarterly)
    if annual.empty:
        return ttm
    annual = annual.sort_index()
    if ttm.dropna().empty:
        return annual
    first_ttm = ttm.dropna().index.min()
    backfill = annual[annual.index < first_ttm]
    if backfill.empty:
        return ttm
    return pd.concat([backfill, ttm]).sort_index()


def _price_history(ticker, start: pd.Timestamp | None) -> pd.DataFrame:
    kwargs: dict = {"auto_adjust": True, "actions": False}
    if start is not None:
        kwargs["start"] = start.strftime("%Y-%m-%d")
    else:
        kwargs["period"] = "max"
    hist = ticker.history(**kwargs)
    if hist is None or hist.empty:
        return pd.DataFrame()
    out = hist[["Close"]].rename(columns={"Close": "price"})
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out.sort_index()


def build_pe_frame(ticker_symbol: str, horizon: Horizon) -> MetricSeries:
    yf = _import_yf()
    if yf is None:
        raise ImportError("yfinance required. Install: pip install 'rallies[viz]'")

    sym = ticker_symbol.upper().strip()
    t = yf.Ticker(sym)
    info = t.info or {}
    name = info.get("longName") or info.get("shortName") or sym

    # Always load full price history; horizon slicing happens after P/E is built.
    prices = _price_history(t, None)
    if prices.empty:
        raise ValueError(f"No price history for {sym}")

    q_eps = _quarterly_eps_series(t)
    annual_eps = _annual_eps_series(t)
    ttm = _eps_for_merge(q_eps, annual_eps)
    if ttm.empty:
        raise ValueError(
            f"Insufficient quarterly EPS for {sym}. Try another ticker or horizon."
        )

    ttm_df = ttm.reset_index()
    ttm_df.columns = ["date", "eps_ttm"]
    ttm_df = ttm_df.sort_values("date")

    px = prices.reset_index()
    date_col = px.columns[0]
    px = px.rename(columns={date_col: "date", "price": "price"})
    px = px.sort_values("date")

    merged = pd.merge_asof(
        px,
        ttm_df,
        on="date",
        direction="backward",
    )
    merged = merged.dropna(subset=["price", "eps_ttm"])
    merged = merged[merged["eps_ttm"] > 0]
    merged["pe"] = merged["price"] / merged["eps_ttm"]

    # YoY growth on quarterly EPS (same quarter prior year)
    q_growth = (q_eps.pct_change(4) * 100).dropna()
    if q_growth.empty:
        annual = getattr(t, "income_stmt", None)
        if annual is not None and not annual.empty:
            a_eps = _quarterly_eps_series_from_stmt(annual)
            if not a_eps.empty:
                q_growth = (a_eps.pct_change(1) * 100).dropna()
    if q_growth.empty:
        from ..yfinance_metrics import growth_rate_percent

        g_val = growth_rate_percent(info, "earningsGrowth", "revenueGrowth")
        if g_val is not None:
            merged["eps_growth_yoy"] = g_val
        else:
            merged["eps_growth_yoy"] = pd.NA
    else:
        gdf = q_growth.reset_index()
        gdf.columns = ["date", "eps_growth_yoy"]
        gdf = gdf.sort_values("date")
        merged = pd.merge_asof(
            merged.sort_values("date"),
            gdf,
            on="date",
            direction="backward",
        )

    growth_pct = merged.get("eps_growth_yoy", pd.Series(dtype=float)).replace(0, pd.NA)
    # PEG (YoY): P/E ÷ YoY quarterly EPS growth — NOT Yahoo "PEG (5yr expected)".
    merged["peg_yoy"] = merged["pe"] / (growth_pct / 100.0)
    merged.loc[growth_pct <= 0, "peg_yoy"] = pd.NA
    merged.loc[merged["peg_yoy"] < 0, "peg_yoy"] = pd.NA
    merged["peg_yoy_raw"] = merged["peg_yoy"]
    merged.loc[merged["peg_yoy"] > 12, "peg_yoy"] = 12.0
    # Backward-compatible aliases for chart panels
    merged["peg"] = merged["peg_yoy"]
    merged["peg_raw"] = merged["peg_yoy_raw"]

    merged = merged.set_index("date")
    merged = add_valuation_derived_columns(merged)
    from .snapshot import build_market_snapshot

    market = build_market_snapshot(info)
    merged = _anchor_latest_trailing_to_yahoo(merged, market)
    _reconcile_trailing_eps_with_yahoo(merged, market)
    return MetricSeries(sym, "valuation", horizon, merged, name, market=market)


def _anchor_latest_trailing_to_yahoo(
    merged: pd.DataFrame, market: dict | None
) -> pd.DataFrame:
    """
    When statement TTM EPS diverges from Yahoo trailingEps (sparse quarters, BRK-B, etc.),
    snap the latest row so snapshot P/E matches key statistics.
    """
    if market is None or merged.empty:
        return merged
    yahoo_eps = market.get("eps_trailing")
    yahoo_pe = market.get("pe_trailing")
    if not yahoo_eps or float(yahoo_eps) <= 0:
        return merged

    out = merged.copy()
    last_idx = out.index[-1]
    calc_eps = float(out.loc[last_idx, "eps_ttm"])
    rel = abs(calc_eps - float(yahoo_eps)) / float(yahoo_eps)
    if rel <= 0.08:
        return out

    price = float(out.loc[last_idx, "price"])
    out.loc[last_idx, "eps_ttm"] = float(yahoo_eps)
    out.loc[last_idx, "pe"] = (
        float(yahoo_pe) if yahoo_pe else price / float(yahoo_eps)
    )

    growth = out.loc[last_idx, "eps_growth_yoy"] if "eps_growth_yoy" in out.columns else pd.NA
    if pd.notna(growth) and float(growth) > 0:
        peg_yoy = out.loc[last_idx, "pe"] / (float(growth) / 100.0)
        out.loc[last_idx, "peg_yoy"] = min(peg_yoy, 12.0) if peg_yoy > 12 else peg_yoy
        out.loc[last_idx, "peg_yoy_raw"] = peg_yoy
        out.loc[last_idx, "peg"] = out.loc[last_idx, "peg_yoy"]
        out.loc[last_idx, "peg_raw"] = peg_yoy

    logger.info(
        "Anchored latest TTM EPS %.2f → Yahoo %.2f (P/E %.2f)",
        calc_eps,
        float(yahoo_eps),
        float(out.loc[last_idx, "pe"]),
    )
    return out


def _reconcile_trailing_eps_with_yahoo(df: pd.DataFrame, market: dict | None) -> None:
    """Warn when computed TTM EPS diverges from Yahoo trailingEps (key statistics parity)."""
    if not market or df.empty:
        return
    yahoo_eps = market.get("eps_trailing")
    yahoo_pe = market.get("pe_trailing")
    if yahoo_eps is None or yahoo_eps <= 0:
        return
    last = df.iloc[-1]
    calc_eps = float(last.get("eps_ttm", 0) or 0)
    if calc_eps <= 0:
        return
    rel_err = abs(calc_eps - float(yahoo_eps)) / float(yahoo_eps)
    if rel_err > 0.08:
        logger.warning(
            "TTM EPS %.2f differs from Yahoo trailingEps %.2f (%.0f%%) — check quarterly statements",
            calc_eps,
            yahoo_eps,
            rel_err * 100,
        )
    if yahoo_pe is not None and last.get("price"):
        calc_pe = float(last["price"]) / calc_eps
        if abs(calc_pe - float(yahoo_pe)) / max(float(yahoo_pe), 1) > 0.08:
            logger.warning(
                "Trailing P/E %.2f differs from Yahoo %.2f",
                calc_pe,
                yahoo_pe,
            )


def peg_for_display(row: pd.Series) -> tuple[float | None, str]:
    """Return (value, label) for summaries — never report capped 12 as exact PEG."""
    if pd.isna(row.get("peg")) and pd.isna(row.get("peg_raw")):
        return None, "—"
    raw = row.get("peg_raw", row.get("peg"))
    if pd.isna(raw):
        return None, "—"
    raw_f = float(raw)
    chart = row.get("peg")
    if pd.notna(chart) and float(chart) >= 12 and raw_f > 12:
        return raw_f, f"{raw_f:.1f} (very high; chart caps display at 12)"
    return raw_f, f"{raw_f:.2f}"


def validate_series_frame(df: pd.DataFrame, horizon_label: str) -> list[str]:
    """Warnings when charts could mislead."""
    warnings: list[str] = []
    if df.empty:
        warnings.append("No rows in selected window.")
        return warnings
    if len(df) < 30:
        warnings.append(f"Only {len(df)} trading days in window — short sample.")

    last = df.iloc[-1]
    if last.get("eps_ttm", 0) and last.get("price") and last.get("pe"):
        implied = float(last["price"]) / float(last["eps_ttm"])
        actual = float(last["pe"])
        if abs(implied - actual) / max(actual, 1) > 0.05:
            warnings.append(
                f"P/E check: price/EPS implies {implied:.1f} vs stored {actual:.1f}."
            )

    peg_pts = df["peg"].notna().sum() if "peg" in df.columns else 0
    if peg_pts < 10:
        warnings.append("Sparse PEG history — growth was often non-positive or missing.")

    if "peg_raw" in df.columns:
        capped = (df["peg_raw"] > 12).sum()
        if capped > len(df) * 0.2:
            warnings.append(
                "PEG (YoY) often exceeds 12 in this window — panel D caps at 12 for readability; "
                "use summary for Yahoo PEG (5yr expected)."
            )

    eps_unique = df["eps_ttm"].nunique() if "eps_ttm" in df.columns else 0
    if eps_unique < 8 and (
        "year" in horizon_label.lower() or "5" in horizon_label
    ):
        warnings.append(
            "EPS steps infrequently in this window (annual backfill may be used for early dates)."
        )
    return warnings


def slice_for_horizon(series: MetricSeries) -> pd.DataFrame:
    df = series.frame
    if series.horizon.start is not None:
        start = pd.Timestamp(series.horizon.start)
        if df.index.tz is not None:
            start = start.tz_localize(df.index.tz)
        df = df[df.index >= start]
    col = "peg" if series.metric == "peg" else "pe"
    return df.dropna(subset=[col])  # valuation dashboards use pe column
