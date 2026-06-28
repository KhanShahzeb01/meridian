"""Portfolio optimization (legacy API + v2 engine)."""

from __future__ import annotations

from .portfolio_optimize import (
    holdings_from_storage,
    parse_optimize_args,
    risk_config,
    run_portfolio_optimization,
    solve_optimal_weights,
)

_has_scipy = False
try:
    import scipy.optimize  # noqa: F401

    _has_scipy = True
except ImportError:
    pass


def optimize_portfolio(
    tickers: list[str],
    expected_returns: list[float] | None = None,
    volatilities: list[float] | None = None,
    risk_free_rate: float = 0.05,
    risk_level: int = 5,
) -> str:
    """
    Optimize a ticker list. With only tickers, uses historical data when available;
    falls back to supplied or default mu/vol for unit tests.
    """
    if len(tickers) < 2:
        return "[yellow]Need at least 2 assets for portfolio optimization.[/yellow]"

    from .portfolio_optimize import PositionInput

    holdings = [
        PositionInput(ticker=t.upper(), quantity=0.0, cost_basis=0.0) for t in tickers
    ]

    if expected_returns and volatilities and _has_scipy:
        return _optimize_from_estimates(
            tickers, expected_returns, volatilities, risk_level, risk_free_rate
        )

    return run_portfolio_optimization(holdings, risk_level=risk_level)


def _optimize_from_estimates(
    tickers: list[str],
    expected_returns: list[float],
    volatilities: list[float],
    risk_level: int,
    risk_free_rate: float,
) -> str:
    """Fast path for tests with explicit return/vol assumptions."""
    import numpy as np

    from .portfolio_optimize import (
        format_optimization_report,
        risk_config,
    )

    n = len(tickers)
    ers = np.array(expected_returns, dtype=float)
    vols = np.array(volatilities, dtype=float)
    corr = np.eye(n) * 0.5 + 0.5
    cov = np.outer(vols, vols) * corr
    sectors = ["Unknown"] * n
    config = risk_config(risk_level)
    eq_w = [1.0 / n] * n
    target_w, err = solve_optimal_weights(list(ers), cov, sectors, config)
    if err:
        return f"[yellow]{err}[/yellow]"
    return format_optimization_report(
        tickers,
        sectors,
        [0.0] * n,
        [None] * n,
        eq_w,
        target_w,
        list(ers),
        ers,
        cov,
        config,
    )


__all__ = [
    "optimize_portfolio",
    "run_portfolio_optimization",
    "holdings_from_storage",
    "parse_optimize_args",
    "risk_config",
]
