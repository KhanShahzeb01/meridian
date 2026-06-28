import logging
import math
from datetime import date, datetime

logger = logging.getLogger(__name__)


def _norm_cdf(x):
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def black_scholes(S, K, T, r, sigma, option_type="call"):
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        price = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    else:
        price = K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)
    return price


def _years_to_expiry(expiry: str) -> float:
    """Years from today to option expiry (minimum one trading day)."""
    try:
        exp = datetime.strptime(str(expiry)[:10], "%Y-%m-%d").date()
    except ValueError:
        return 30 / 365.0
    days = (exp - date.today()).days
    return max(days / 365.0, 1 / 365.0)


def _normalize_iv(iv, default: float = 0.30) -> float:
    """yfinance IV is usually decimal (0.35 = 35%); clamp obvious bad quotes."""
    try:
        value = float(iv)
    except (TypeError, ValueError):
        return default
    if value <= 0:
        return default
    if value > 5:
        return default
    return value


def price_options(
    ticker: str,
    current_price: float,
    option_data: list[dict] | None = None,
    risk_free_rate: float = 0.05,
    expiry: str | None = None,
) -> str:
    if option_data is None:
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            chains = t.options
            if not chains:
                return f"[yellow]No options chain found for {ticker}.[/yellow]"
            nearest = chains[0]
            opt = t.option_chain(nearest)
            calls = [
                {**row, "type": "call"}
                for row in opt.calls.head(10).to_dict("records")
            ]
            puts = [
                {**row, "type": "put"}
                for row in opt.puts.head(10).to_dict("records")
            ]
            option_data = calls + puts
            expiry = nearest
        except Exception as e:
            return f"[yellow]Could not fetch options: {e}[/yellow]"
    else:
        expiry = expiry or "N/A"

    T = _years_to_expiry(expiry) if expiry and expiry != "N/A" else 30 / 365.0

    from ..metric_units import OPTIONS_UNITS_NOTE

    lines = [f"[bold]Options Chain — {ticker} ({expiry})[/bold]", ""]
    lines.append(f"  [dim]{OPTIONS_UNITS_NOTE}[/dim]")
    lines.append(f"  Current Price ($/share): ${current_price:.2f}")
    lines.append(f"  Risk-Free Rate (%): {risk_free_rate * 100:.1f}%")
    lines.append(f"  Time to Expiry (days): {T * 365:.1f}")
    lines.append("")

    lines.append("  [bold]Calls[/bold]")
    lines.append(f"  {'Strike$':>8} {'Last$':>8} {'IV%':>8} {'BS$':>10}")
    for o in option_data:
        if o.get("type", "").lower() == "put":
            continue
        strike = o.get("strike", 0)
        last = o.get("lastPrice", 0)
        iv = _normalize_iv(o.get("impliedVolatility", 0.3))
        bs_price = black_scholes(current_price, strike, T, risk_free_rate, iv, "call")
        lines.append(
            f"  ${strike:<6.0f} {last:<8.2f} {iv * 100:<7.1f}% ${bs_price:<8.2f}"
        )

    lines.append("")
    lines.append("  [bold]Puts[/bold]")
    lines.append(f"  {'Strike$':>8} {'Last$':>8} {'IV%':>8} {'BS$':>10}")
    for o in option_data:
        if o.get("type", "").lower() == "call":
            continue
        strike = o.get("strike", 0)
        last = o.get("lastPrice", 0)
        iv = _normalize_iv(o.get("impliedVolatility", 0.3))
        bs_price = black_scholes(current_price, strike, T, risk_free_rate, iv, "put")
        lines.append(
            f"  ${strike:<6.0f} {last:<8.2f} {iv * 100:<7.1f}% ${bs_price:<8.2f}"
        )

    return "\n".join(lines)
