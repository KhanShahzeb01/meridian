import logging

logger = logging.getLogger(__name__)


def fetch_free_cash_flow_yfinance(ticker) -> tuple[float | None, str]:
    """
    Resolve positive FCF from yfinance info or cash-flow statement.

    Returns (fcf_usd, source_label). Prefer TTM ``info.freeCashflow`` (absolute USD).
    Fallback: latest fiscal-year column OCF + CapEx (capex is negative in yfinance).
    """
    info = ticker.info or {}
    fcf = info.get("freeCashflow")
    if fcf and float(fcf) > 0:
        return float(fcf), "TTM (info.freeCashflow, USD)"

    cf = getattr(ticker, "cashflow", None)
    if cf is None or cf.empty:
        return None, "unavailable"

    if "Operating Cash Flow" not in cf.index:
        return None, "unavailable"

    col = cf.columns[0]
    period = str(col.date())[:10] if hasattr(col, "date") else str(col)[:10]
    ocf = float(cf.loc["Operating Cash Flow", col])
    capex = 0.0
    if "Capital Expenditure" in cf.index:
        capex = float(cf.loc["Capital Expenditure", col])
    elif "Capital Expenditures" in cf.index:
        capex = float(cf.loc["Capital Expenditures", col])

    fcf = ocf + capex
    if fcf > 0:
        return fcf, f"latest fiscal year {period} (OCF+CapEx, USD)"
    return None, "unavailable"


def _try_import_numpy():
    try:
        import numpy as np
        return np
    except ImportError:
        return None


def dcf_valuation(
    ticker: str,
    free_cash_flow: float | None = None,
    growth_rate: float = 0.10,
    terminal_growth: float = 0.03,
    wacc: float = 0.09,
    projection_years: int = 5,
    shares_outstanding: float | None = None,
    cash_and_equivalents: float = 0,
    total_debt: float = 0,
    current_price: float | None = None,
    fcf_source: str = "TTM (USD)",
) -> tuple[float | None, str]:
    from ..metric_units import DCF_UNITS_NOTE, normalize_rate_decimal

    np = _try_import_numpy()
    if np is None:
        return None, "numpy is required for DCF. Install with: pip install numpy"

    growth_rate = normalize_rate_decimal(growth_rate)
    wacc = normalize_rate_decimal(wacc)
    terminal_growth = normalize_rate_decimal(terminal_growth)

    if free_cash_flow is None or free_cash_flow <= 0:
        return None, (
            f"{ticker} has no positive free cash flow.\n"
            f"DCF requires positive FCF — this company is likely pre-profit or reinvesting heavily.\n"
            f"Alternative approaches: /peers {ticker} (comps) or /quote {ticker} (P/S, P/B)."
        )

    fcf_values = []
    for y in range(1, projection_years + 1):
        fcf = free_cash_flow * ((1 + growth_rate) ** y)
        fcf_values.append(fcf)

    pv_factors = [(1 + wacc) ** y for y in range(1, projection_years + 1)]
    pv_fcfs = [fcf / pv_factors[i] for i, fcf in enumerate(fcf_values)]

    terminal_value = fcf_values[-1] * (1 + terminal_growth) / (wacc - terminal_growth) if wacc > terminal_growth else fcf_values[-1] * 15
    pv_terminal = terminal_value / pv_factors[-1]

    enterprise_value = sum(pv_fcfs) + pv_terminal
    equity_value = enterprise_value - total_debt + cash_and_equivalents

    if shares_outstanding and shares_outstanding > 0:
        fair_value_per_share = equity_value / shares_outstanding
    else:
        return equity_value, "Shares outstanding required for per-share value. Enterprise value shown."

    upside = ((fair_value_per_share / current_price) - 1) * 100 if current_price and current_price > 0 else 0

    fcf_b = free_cash_flow / 1e9
    shares_line = (
        f"    Shares: {shares_outstanding / 1e9:.2f}B (count)\n"
        if shares_outstanding
        else "    Shares: n/a\n"
    )
    cash_debt_line = (
        f"    Cash: ${cash_and_equivalents / 1e9:.2f}B · Debt: ${total_debt / 1e9:.2f}B (USD)\n"
    )
    details = (
        f"[bold]DCF Valuation — {ticker}[/bold]\n"
        f"  [dim]{DCF_UNITS_NOTE}[/dim]\n"
        f"  Fair Value: [bold]${fair_value_per_share:.2f}[/bold] ($/share)\n"
        f"  Current Price: ${current_price:.2f} ($/share)\n"
        f"  Upside/Downside: [{'green' if upside > 0 else 'red'}]{upside:+.1f}%[/{'green' if upside > 0 else 'red'}]\n"
        f"  Enterprise Value: ${enterprise_value / 1e9:.2f}B (USD)\n"
        f"  Equity Value: ${equity_value / 1e9:.2f}B (USD)\n"
        f"  Inputs:\n"
        f"    Base FCF: ${fcf_b:.2f}B — {fcf_source}\n"
        f"{shares_line}"
        f"{cash_debt_line}"
        f"  Assumptions (rates as %):\n"
        f"    FCF Growth: {growth_rate * 100:.0f}%\n"
        f"    WACC: {wacc * 100:.0f}%\n"
        f"    Terminal Growth: {terminal_growth * 100:.0f}%\n"
        f"    Projection Period: {projection_years} years\n"
    )

    return fair_value_per_share, details
