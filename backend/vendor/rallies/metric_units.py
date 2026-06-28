"""Display labels and unit conventions for rallies metrics."""

from __future__ import annotations

METRIC_LABELS: dict[str, str] = {
    # Prices & size
    "price": "Price ($/share)",
    "prev_close": "Prev close ($/share)",
    "day_high": "Day high ($/share)",
    "day_low": "Day low ($/share)",
    "market_cap": "Market cap (USD)",
    "volume": "Volume (shares)",
    # Returns & changes
    "change_pct": "Change (1-day, %)",
    "change_1d_pct": "Change (1-day, %)",
    "mom_3m_pct": "Return (3-month, %)",
    # Valuation ratios (dimensionless)
    "pe": "P/E (trailing TTM)",
    "pe_trailing": "P/E (trailing TTM)",
    "pe_forward": "Forward P/E",
    "peg_5yr": "PEG (5yr expected)",
    "pb": "P/B (ratio)",
    "ps": "P/S TTM (ratio)",
    "ev_to_ebitda": "EV/EBITDA (ratio)",
    # Per-share earnings
    "eps": "EPS (trailing TTM, $/share)",
    "eps_trailing": "EPS (trailing TTM, $/share)",
    "eps_forward": "EPS (forward, $/share)",
    "eps_fiscal": "EPS (fiscal annual, $/share)",
    # Yields
    "dividend_yield_pct": "Dividend yield (%, annualized)",
    # Growth & margins (Yahoo TTM)
    "revenue_growth_pct": "Revenue growth (TTM YoY, %)",
    "earnings_growth_pct": "Earnings growth (TTM YoY, %)",
    "profit_margin_pct": "Profit margin (TTM, %)",
    "roe_pct": "ROE (TTM, %)",
    "roa_pct": "ROA (TTM, %)",
    "rev_growth_fiscal": "Revenue growth (fiscal YoY, %)",
    "net_margin_fiscal": "Net margin (fiscal, %)",
    # Screener / deep metrics
    "rev_growth": "Revenue growth (TTM decimal)",
    "profit_margin": "Profit margin (TTM decimal)",
    "roe": "ROE (TTM decimal)",
    "de": "Debt/equity (Yahoo mrq)",
    # Portfolio
    "quantity": "Qty (shares)",
    "cost_basis": "Avg cost ($/share)",
    "total_cost": "Total cost (USD)",
    "value": "Value (USD)",
    "pl": "P&L (USD)",
    "pl_pct": "P&L (%)",
    # DCF
    "fcf": "Base FCF (USD)",
    "fair_value": "Fair value ($/share)",
    "enterprise_value": "Enterprise value (USD)",
    "equity_value": "Equity value (USD)",
    "wacc": "WACC (%)",
    "growth_rate": "FCF growth (%)",
    "terminal_growth": "Terminal growth (%)",
    # Quant analysis
    "total_return": "Total return (%)",
    "annual_return": "CAGR (%)",
    "volatility": "Volatility (ann., %)",
    "sharpe": "Sharpe ratio",
    "sortino": "Sortino ratio",
    "calmar": "Calmar ratio",
    "max_drawdown": "Max drawdown (%)",
    "win_rate": "Win rate (%)",
    # Options
    "iv": "Implied vol (%)",
    "strike": "Strike ($/share)",
    "bs_price": "Black-Scholes ($/share)",
    # Earnings
    "surprise_pct": "Surprise (%)",
    "reported_eps": "Reported EPS ($/share, quarter)",
    "eps_estimate": "Estimate EPS ($/share, quarter)",
    # Targets & range
    "target_mean": "Target mean ($/share)",
    "target_upside_pct": "Upside to mean (%)",
    "fifty_two_week_range": "52-week range ($/share)",
    "rating": "Analyst rating",
    # VIX / index
    "vix": "VIX (index)",
    # Alerts
    "threshold_pct": "Alert threshold (%)",
    "base_price": "Alert base ($/share)",
}

QUOTE_UNITS_NOTE = (
    "Trailing P/E, EPS, PEG from Yahoo key statistics (TTM). "
    "Change = 1-day %. Dividend yield = dividendRate ÷ price."
)

FINANCIALS_UNITS_NOTE = (
    "Annual fiscal periods (newest first). Amounts in USD. "
    "EPS = fiscal diluted $/share (not trailing TTM). "
    "Rev growth & net margin = fiscal YoY (computed)."
)

EARNINGS_UNITS_NOTE = (
    "Quarterly reported vs estimate EPS ($/share). "
    "Surprise % from yfinance (ratio→%). Not GAAP TTM EPS used for P/E."
)

DCF_UNITS_NOTE = (
    "FCF in absolute USD (TTM from info when available). "
    "Growth & WACC as decimal rates (0.10 = 10%; you may also pass 10)."
)

ANALYSIS_UNITS_NOTE = (
    "1y daily close prices. Returns & vol annualized (252 trading days). "
    "Sharpe/Sortino use rf=5% and arithmetic mean return."
)

OPTIONS_UNITS_NOTE = (
    "IV from chain (decimal). Black-Scholes: T in years, r=5%."
)

OPTIMIZE_UNITS_NOTE = (
    "μ and Σ annualized from daily returns. Expected return blend: "
    "45% 2y history · 30% 6mo momentum · 25% analyst upside."
)

SCREENER_UNIT_LEGEND = (
    "Units: Price $/sh · P/E ratios dimensionless · "
    "RevGr/Margin/ROE: Yahoo TTM (input decimal, shown as %) · "
    "D/E: Yahoo mrq · Mom3M: 3mo total return % · MktCap USD"
)

PORTFOLIO_UNITS_NOTE = "Qty in shares; prices & P&L in USD."

PEERS_UNITS_NOTE = "Rev growth & margin: Yahoo TTM YoY %. PEG: 5yr expected."


def label(key: str, default: str | None = None) -> str:
    """Human-readable column/row label with units."""
    return METRIC_LABELS.get(key, default or key.replace("_", " ").title())


def normalize_rate_decimal(value: float) -> float:
    """
    Accept rate as decimal (0.10) or whole percent (10 → 0.10).
    Values > 100 are left unchanged (caller error).
    """
    v = float(value)
    if 1.0 < v <= 100.0:
        return v / 100.0
    return v


def format_decimal_as_pct(decimal: float | None, digits: int = 1) -> str:
    """Format yfinance-style decimal (0.133) as percent string without suffix."""
    if decimal is None:
        return "—"
    return f"{float(decimal) * 100:.{digits}f}"


def format_pct_value(pct: float | None, digits: int = 1) -> str:
    """Format value already in percent (12.5 = 12.5%)."""
    if pct is None:
        return "—"
    return f"{float(pct):.{digits}f}"
