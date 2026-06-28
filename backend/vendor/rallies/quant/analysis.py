import logging

logger = logging.getLogger(__name__)


def _try_yf():
    try:
        import yfinance as yf
        return yf
    except ImportError:
        return None


def quant_analysis(ticker: str, price_history: list[float] | None = None) -> str:
    has_numpy = True
    try:
        import numpy as np
    except ImportError:
        has_numpy = False

    has_quantstats = True
    try:
        import quantstats as qs
    except ImportError:
        has_quantstats = False

    has_yf = True
    try:
        import yfinance as yf
    except ImportError:
        has_yf = False

    if not has_numpy:
        return "[yellow]Quant analysis requires numpy. Install: pip install numpy[/yellow]"

    import numpy as np

    if price_history is None:
        yf = _try_yf()
        if yf is not None:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="1y")
                if not hist.empty:
                    price_history = hist["Close"].tolist()
            except Exception:
                pass

    if not price_history or len(price_history) < 20:
        return f"[yellow]Insufficient price history for {ticker}. Need at least 20 data points.[/yellow]"

    prices = np.array(price_history)
    returns = np.diff(prices) / prices[:-1]
    rf = 0.05
    trading_days = 252

    total_return = (prices[-1] / prices[0] - 1) * 100
    annual_return = (prices[-1] / prices[0]) ** (trading_days / len(prices)) - 1
    arith_annual = float(np.mean(returns)) * trading_days
    volatility = float(np.std(returns, ddof=1)) * np.sqrt(trading_days) * 100
    vol_decimal = volatility / 100
    sharpe = (arith_annual - rf) / vol_decimal if vol_decimal > 0 else 0
    max_drawdown = _compute_max_drawdown(prices) * 100
    calmar = annual_return / (abs(max_drawdown) / 100) if max_drawdown < 0 else 0
    sortino = _compute_sortino(returns, rf=rf, trading_days=trading_days)
    avg_daily_return = np.mean(returns) * 100
    win_rate = np.sum(returns > 0) / len(returns) * 100

    from ..metric_units import ANALYSIS_UNITS_NOTE

    lines = [
        f"[bold]Quant Analysis — {ticker}[/bold]",
        f"  [dim]{ANALYSIS_UNITS_NOTE}[/dim]",
        "",
        f"  Period: {len(prices)} trading days (~{len(prices) / trading_days:.1f} years)",
        "",
        "  [bold]Performance[/bold]",
        f"  Total Return (%): [{'green' if total_return > 0 else 'red'}]{total_return:+.1f}%[/{'green' if total_return > 0 else 'red'}]",
        f"  CAGR (%): [{'green' if annual_return > 0 else 'red'}]{annual_return*100:+.1f}%[/{'green' if annual_return > 0 else 'red'}]" if annual_return < 1 else f"  CAGR (%): [{'green' if annual_return > 0 else 'red'}]{annual_return*100:+.1f}%[/{'green' if annual_return > 0 else 'red'}]",
        f"  Avg Daily Return (%): {avg_daily_return:+.3f}%",
        f"  Win Rate (%): {win_rate:.1f}%",
        "",
        "  [bold]Risk[/bold]",
        f"  Volatility ann. (%): {volatility:.1f}%",
        f"  Max Drawdown (%): [red]{max_drawdown:.1f}%[/red]",
        "",
        "  [bold]Risk-Adjusted[/bold]",
        f"  Sharpe (rf=5%): [{'green' if sharpe > 1 else 'yellow' if sharpe > 0 else 'red'}]{sharpe:.2f}[/{'green' if sharpe > 1 else 'yellow' if sharpe > 0 else 'red'}]",
        f"  Sortino (rf=5%): {sortino:.2f}",
        f"  Calmar (CAGR/max DD): {calmar:.2f}",
        "",
    ]

    summary = _build_layman_summary(ticker, total_return, annual_return, volatility, sharpe, max_drawdown, win_rate)
    lines.append(f"  [bold]Summary[/bold]\n  {summary}")
    lines.append("")

    if has_quantstats:
        lines.append("  [dim]Install quantstats for detailed reports: pip install quantstats[/dim]")

    return "\n".join(lines)


def _build_layman_summary(ticker, total_return, annual_return, volatility, sharpe, max_drawdown, win_rate):
    parts = []

    if total_return > 30:
        parts.append(f"[white]{ticker}[/white] had a [green]strong year[/green] — up {total_return:.0f}%, well above most stocks.")
    elif total_return > 10:
        parts.append(f"[white]{ticker}[/white] had a [green]decent year[/green] — up {total_return:.0f}%, solid but not exceptional.")
    elif total_return > 0:
        parts.append(f"[white]{ticker}[/white] [green]barely broke even[/green] — up just {total_return:.0f}%, lagging the broader market.")
    else:
        parts.append(f"[white]{ticker}[/white] [red]lost money[/red] — down {abs(total_return):.0f}% over the period.")

    if volatility > 80:
        parts.append(f"It is [red]extremely volatile[/red] ({volatility:.0f}% annualized) — expect wild swings of 5-10% in any given week.")
    elif volatility > 50:
        parts.append(f"It is [yellow]highly volatile[/yellow] ({volatility:.0f}% annualized) — price moves of 3-5% are normal.")
    elif volatility > 30:
        parts.append(f"Volatility is [yellow]moderate[/yellow] ({volatility:.0f}% annualized) — similar to an average tech stock.")
    else:
        parts.append(f"Volatility is [green]low[/green] ({volatility:.0f}% annualized) — price action is relatively calm.")

    if sharpe > 1.5:
        parts.append(f"The Sharpe ratio of {sharpe:.2f} is [green]excellent[/green] — you are getting well compensated for the risk taken.")
    elif sharpe > 0.7:
        parts.append(f"The Sharpe ratio of {sharpe:.2f} is [yellow]acceptable[/yellow] — returns somewhat justify the risk.")
    elif sharpe > 0:
        parts.append(f"The Sharpe ratio of {sharpe:.2f} is [red]weak[/red] — most of the return comes from taking risk, not from a good business.")
    else:
        parts.append(f"The Sharpe ratio is [red]negative[/red] — you'd have been better off in risk-free Treasuries.")

    if max_drawdown < -50:
        parts.append(f"[red]Warning[/red]: It fell {abs(max_drawdown):.0f}% from peak to trough at one point — investors need strong conviction to hold through that.")
    elif max_drawdown < -30:
        parts.append(f"At its worst it dropped {abs(max_drawdown):.0f}% — a [yellow]painful but survivable[/yellow] drawdown.")
    else:
        parts.append(f"The worst drop was {abs(max_drawdown):.0f}% — [green]relatively mild[/green] compared to most stocks.")

    return " ".join(parts)


def _compute_max_drawdown(prices):
    import numpy as np
    peak = np.maximum.accumulate(prices)
    drawdown = (prices - peak) / peak
    return np.min(drawdown)


def _compute_sortino(returns, rf=0.05, trading_days=252):
    """Sortino = (annualized arithmetic return - rf) / annualized downside deviation."""
    import numpy as np

    mar_daily = rf / trading_days
    downside = np.minimum(0.0, returns - mar_daily)
    semi_var = float(np.mean(downside ** 2))
    if semi_var <= 0:
        return 10.0
    downside_dev = float(np.sqrt(semi_var)) * np.sqrt(trading_days)
    if downside_dev <= 0:
        return 10.0
    arith_annual = float(np.mean(returns)) * trading_days
    return (arith_annual - rf) / downside_dev
