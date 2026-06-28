"""
Portfolio optimization using live holdings, historical returns, sector limits,
and a user risk dial (1 = conservative, 10 = aggressive).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_has_scipy = False
try:
    import scipy.optimize  # noqa: F401

    _has_scipy = True
except ImportError:
    pass


@dataclass
class PositionInput:
    ticker: str
    quantity: float = 0.0
    cost_basis: float = 0.0
    sector: str = "Unknown"
    price: float | None = None

    @property
    def market_value(self) -> float:
        if self.price is not None and self.quantity > 0:
            return float(self.quantity) * float(self.price)
        return 0.0


@dataclass
class OptimizeConfig:
    risk_level: int = 5
    max_name_weight: float = 0.0
    max_sector_weight: float = 0.0
    risk_aversion: float = 0.0


def parse_optimize_args(prompt: str) -> tuple[int, list[str]]:
    """Parse `/optimize [risk N] [TICKER,TICKER,...]`."""
    text = prompt.strip()
    if text.lower().startswith("/optimize"):
        text = text[len("/optimize") :].strip()

    risk_level = 5
    match = re.search(r"\brisk\s+(\d{1,2})\b", text, re.IGNORECASE)
    if match:
        risk_level = max(1, min(10, int(match.group(1))))
        text = (text[: match.start()] + text[match.end() :]).strip()

    tickers: list[str] = []
    if text:
        normalized = text.replace(" ", ",")
        tickers = [
            t.strip().upper()
            for t in normalized.split(",")
            if t.strip() and not t.strip().lower().startswith("risk")
        ]
    return risk_level, tickers


def risk_config(risk_level: int) -> OptimizeConfig:
    """Map 1–10 dial to concentration limits and mean-variance risk aversion."""
    r = max(1, min(10, int(risk_level)))
    # Low risk: smaller positions, tighter sectors, high penalty on volatility
    t = (r - 1) / 9.0
    max_name = 0.12 + t * 0.28  # 12% .. 40%
    max_sector = 0.22 + t * 0.38  # 22% .. 60%
    risk_aversion = 12.0 - t * 10.5  # 12 .. 1.5
    return OptimizeConfig(
        risk_level=r,
        max_name_weight=max_name,
        max_sector_weight=max_sector,
        risk_aversion=risk_aversion,
    )


def _import_yfinance():
    try:
        import logging as _yl

        import yfinance as yf

        _yl.getLogger("yfinance").setLevel(_yl.CRITICAL)
        return yf
    except ImportError:
        return None


def _import_numpy():
    try:
        import numpy as np

        return np
    except ImportError:
        return None


def fetch_position_metadata(
    positions: list[PositionInput],
    data_registry=None,
) -> list[PositionInput]:
    """Fill price and sector from yfinance or data registry."""
    yfs = data_registry.get_source("yfinance") if data_registry else None
    yf = _import_yfinance()
    out: list[PositionInput] = []
    for pos in positions:
        sector = pos.sector or "Unknown"
        price = pos.price
        if yfs:
            q = yfs.get_quote(pos.ticker)
            if q and "error" not in q:
                price = price or q.get("price")
                sector = q.get("sector") or sector
        if (price is None or sector == "Unknown") and yf:
            try:
                info = yf.Ticker(pos.ticker).info or {}
                price = price or info.get("currentPrice") or info.get("regularMarketPrice")
                sector = info.get("sector") or sector
            except Exception:
                logger.debug("metadata fetch failed for %s", pos.ticker)
        out.append(
            PositionInput(
                ticker=pos.ticker,
                quantity=pos.quantity,
                cost_basis=pos.cost_basis,
                sector=sector or "Unknown",
                price=float(price) if price else None,
            )
        )
    return out


def fetch_return_matrix(
    tickers: list[str],
    period: str = "2y",
):
    """Annualized mean returns vector and covariance matrix from daily prices."""
    np = _import_numpy()
    yf = _import_yfinance()
    if np is None:
        return None, None, None, "numpy is required. Install: pip install numpy"
    if yf is None:
        return None, None, None, "yfinance is required. Install: pip install yfinance"

    if len(tickers) < 2:
        return None, None, None, "Need at least 2 tickers with price history."

    raw = yf.download(
        tickers,
        period=period,
        interval="1d",
        group_by="column",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if raw is None or raw.empty:
        return None, None, None, "Could not download price history."

    if len(tickers) == 1:
        closes = raw[["Close"]] if "Close" in raw.columns else raw
        closes.columns = [tickers[0]]
    else:
        if isinstance(raw.columns, __import__("pandas").MultiIndex):
            closes = raw["Close"]
        else:
            closes = raw

    closes = closes.dropna(how="all").ffill().dropna(how="any")
    if len(closes) < 60:
        return None, None, None, "Not enough history (need ~60 trading days)."

    daily = closes.pct_change().dropna()
    usable = [t for t in tickers if t in daily.columns]
    if len(usable) < 2:
        return None, None, None, "Fewer than 2 tickers have overlapping history."

    daily = daily[usable]
    mu = daily.mean().values * 252
    cov = daily.cov().values * 252
    sectors = {t: "Unknown" for t in usable}
    return np.array(mu), np.array(cov), usable, None


def estimate_expected_returns(
    tickers: list[str],
    historical_mu,
    data_registry=None,
) -> list[float]:
    """
    Blend historical return, 6-month momentum, and analyst upside (when available).
    """
    np = _import_numpy()
    yf = _import_yfinance()
    if np is None:
        return list(historical_mu)

    blended = []
    for i, ticker in enumerate(tickers):
        hist = float(historical_mu[i])
        momentum = 0.0
        upside = 0.0

        if yf:
            try:
                hist_px = yf.Ticker(ticker).history(period="6mo", auto_adjust=True)
                if hist_px is not None and len(hist_px) > 20:
                    start = float(hist_px["Close"].iloc[0])
                    end = float(hist_px["Close"].iloc[-1])
                    if start > 0:
                        momentum = (end / start) ** 2 - 1  # annualize ~6m move
                info = yf.Ticker(ticker).info or {}
                price = info.get("currentPrice") or info.get("regularMarketPrice")
                target = info.get("targetMeanPrice")
                if price and target and price > 0:
                    upside = (float(target) / float(price)) - 1.0
                    upside = max(-0.5, min(0.8, upside))
            except Exception:
                logger.debug("expected return extras failed for %s", ticker)

        est = 0.45 * hist + 0.30 * momentum + 0.25 * upside
        blended.append(max(-0.25, min(0.60, est)))

    return blended


def _effective_name_cap(config: OptimizeConfig, n_assets: int) -> float:
    """Minimum per-name cap so weights can sum to 100%."""
    if n_assets <= 0:
        return config.max_name_weight
    return max(config.max_name_weight, 1.0 / n_assets)


def _effective_sector_cap(config: OptimizeConfig, n_sectors: int) -> float:
    """Minimum sector cap so weights can sum to 100% across sectors."""
    if n_sectors <= 0:
        return config.max_sector_weight
    return max(config.max_sector_weight, 1.0 / n_sectors)


def _feasible_initial_weights(
    n: int,
    sector_indices: dict[str, list[int]],
    config: OptimizeConfig,
    np,
) -> "np.ndarray":
    """Start from equal split within sectors, respecting name and sector caps."""
    sector_cap = _effective_sector_cap(config, len(sector_indices))
    w = np.zeros(n)
    for indices in sector_indices.values():
        if not indices:
            continue
        name_cap = _effective_name_cap(config, n)
        each = min(name_cap, sector_cap / len(indices))
        w[indices] = each
    if w.sum() <= 0:
        return np.ones(n) / n
    return _project_weights(w / w.sum(), sector_indices, config, np, name_cap)


def solve_optimal_weights(
    expected_returns,
    cov_matrix,
    sectors: list[str],
    config: OptimizeConfig,
) -> tuple[list[float] | None, str | None]:
    """Mean-variance optimize: maximize return - λ * variance with sector caps."""
    if not _has_scipy:
        return None, "Portfolio optimization requires scipy. Install: pip install scipy"

    np = _import_numpy()
    if np is None:
        return None, "numpy is required."

    import scipy.optimize as opt
    from scipy.optimize import Bounds, LinearConstraint

    n = len(expected_returns)
    mu = np.array(expected_returns, dtype=float)
    cov = np.array(cov_matrix, dtype=float) + np.eye(n) * 1e-8
    lam = float(config.risk_aversion)

    def objective(w):
        w = np.array(w)
        ret = float(np.dot(w, mu))
        var = float(np.dot(w, np.dot(cov, w)))
        return -(ret - lam * var)

    sector_indices: dict[str, list[int]] = {}
    for idx, sec in enumerate(sectors):
        sector_indices.setdefault(sec or "Unknown", []).append(idx)

    sector_cap = _effective_sector_cap(config, len(sector_indices))
    name_cap = _effective_name_cap(config, n)
    bounds = Bounds(0.0, name_cap)
    x0 = _feasible_initial_weights(n, sector_indices, config, np)
    constraints = [LinearConstraint(np.ones((1, n)), 1.0, 1.0)]
    if sector_indices:
        a_ub = []
        for indices in sector_indices.values():
            row = np.zeros(n)
            row[indices] = 1.0
            a_ub.append(row)
        constraints.append(
            LinearConstraint(
                np.array(a_ub),
                -np.inf,
                np.full(len(a_ub), sector_cap),
            )
        )

    result = None
    for method in ("trust-constr", "SLSQP"):
        try:
            if method == "trust-constr":
                result = opt.minimize(
                    objective,
                    x0,
                    method=method,
                    bounds=bounds,
                    constraints=constraints,
                    options={"maxiter": 800, "gtol": 1e-8},
                )
            else:
                legacy = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
                for indices in sector_indices.values():
                    cap = sector_cap

                    def _sector_cap(w, idxs=indices, limit=cap):
                        return limit - float(np.sum(w[idxs]))

                    legacy.append({"type": "ineq", "fun": _sector_cap})
                result = opt.minimize(
                    objective,
                    x0,
                    method=method,
                    bounds=[(0.0, name_cap)] * n,
                    constraints=legacy,
                    options={"maxiter": 600, "ftol": 1e-8},
                )
            if result.success:
                break
        except Exception as exc:
            logger.debug("optimizer %s failed: %s", method, exc)

    if result is None or not result.success:
        inv_vol = 1.0 / np.sqrt(np.maximum(np.diag(cov), 1e-12))
        w = inv_vol / inv_vol.sum()
        # Tilt toward higher expected return as risk dial rises
        tilt = (config.risk_level - 1) / 9.0
        score = np.maximum(mu, 0) + 0.01
        w = (1 - tilt) * w + tilt * (score / score.sum())
        w = np.clip(w, 0, name_cap)
        if w.sum() <= 0:
            w = np.ones(n) / n
        w = _project_weights(w, sector_indices, config, np, name_cap)
        return list(w), None

    w = _project_weights(
        np.clip(result.x, 0, None),
        sector_indices,
        config,
        np,
        name_cap,
    )
    return list(w), None


def _project_weights(
    w,
    sector_indices: dict[str, list[int]],
    config: OptimizeConfig,
    np,
    name_cap: float | None = None,
):
    """Enforce per-name and per-sector caps; renormalize to 100%."""
    w = np.maximum(np.array(w, dtype=float), 0.0)
    n = len(w)
    if w.sum() <= 0:
        return np.ones(n) / n
    w = w / w.sum()

    name_cap = name_cap if name_cap is not None else _effective_name_cap(config, n)
    sector_cap = _effective_sector_cap(config, len(sector_indices))
    index_sector: dict[int, list[int]] = {}
    for indices in sector_indices.values():
        for i in indices:
            index_sector[i] = indices

    for _ in range(128):
        prev = w.copy()
        w = np.clip(w, 0.0, name_cap)

        for indices in sector_indices.values():
            s = float(w[indices].sum())
            if s > sector_cap + 1e-9:
                w[indices] *= sector_cap / s

        slack = 1.0 - float(w.sum())
        if slack > 1e-6:
            room: list[tuple[int, float]] = []
            for i in range(n):
                indices = index_sector.get(i)
                name_room = name_cap - w[i]
                sec_room = (
                    sector_cap - float(w[indices].sum())
                    if indices is not None
                    else 1.0
                )
                r = min(name_room, sec_room)
                if r > 1e-9:
                    room.append((i, r))
            if room:
                total_room = sum(r for _, r in room)
                for i, r in room:
                    w[i] += slack * (r / total_room)

        total = float(w.sum())
        if total > 1e-12:
            w = w / total
        if np.allclose(w, prev, atol=1e-7):
            break

    w = np.clip(w, 0.0, name_cap)
    if w.sum() > 0:
        w = w / w.sum()
    return w


def _portfolio_stats(weights, mu, cov, np, risk_free_rate: float = 0.05):
    w = np.array(weights)
    ret = float(np.dot(w, mu))
    vol = float(np.sqrt(np.dot(w, np.dot(cov, w))))
    sharpe = (ret - risk_free_rate) / vol if vol > 1e-9 else 0.0
    return ret, vol, sharpe


def _report_column_widths(tickers: list[str], sectors: list[str]) -> tuple[int, int]:
    """Fixed column widths for holdings + suggested-trades tables."""
    ticker_w = max(6, max((len(t) for t in tickers), default=6))
    sector_w = min(24, max(18, max((len(s) for s in sectors), default=18)))
    return ticker_w, sector_w


def format_optimization_report(
    tickers: list[str],
    sectors: list[str],
    quantities: list[float],
    prices: list[float | None],
    current_weights: list[float],
    target_weights: list[float],
    expected_returns: list[float],
    mu,
    cov,
    config: OptimizeConfig,
) -> str:
    np = _import_numpy()
    if np is None:
        return "[red]numpy required[/red]"

    cur_ret, cur_vol, cur_sharpe = _portfolio_stats(current_weights, mu, cov, np)
    tgt_ret, tgt_vol, tgt_sharpe = _portfolio_stats(target_weights, mu, cov, np)

    total_value = sum(
        (q * p if p else 0.0) for q, p in zip(quantities, prices, strict=False)
    )

    n = len(tickers)
    n_sectors = len(set(sectors))
    eff_name = _effective_name_cap(config, n)
    eff_sector = _effective_sector_cap(config, n_sectors)
    limit_note = ""
    if eff_name > config.max_name_weight + 0.001 or eff_sector > config.max_sector_weight + 0.001:
        limit_note = (
            f"  [dim]With {n} names, effective caps are "
            f"{eff_name * 100:.0f}% / stock and {eff_sector * 100:.0f}% / sector "
            f"(need more holdings to reach tighter risk-{config.risk_level} limits).[/dim]\n"
        )

    from ..metric_units import OPTIMIZE_UNITS_NOTE

    lines = [
        "[bold cyan]Portfolio optimization[/bold cyan]",
        f"  [dim]{OPTIMIZE_UNITS_NOTE}[/dim]",
        f"  Risk dial: [white]{config.risk_level}/10[/white] "
        f"([dim]{'conservative' if config.risk_level <= 3 else 'balanced' if config.risk_level <= 7 else 'aggressive'}[/dim])",
        f"  Limits: max [white]{config.max_name_weight * 100:.0f}%[/white] per stock, "
        f"[white]{config.max_sector_weight * 100:.0f}%[/white] per sector",
        limit_note,
        "",
        "[bold]Expected return model[/bold] [dim](per ticker, annualized)[/dim]",
        "  45% trailing 2y history · 30% 6-month momentum · 25% analyst target upside",
        "",
        "[bold]Current vs optimized (model)[/bold]",
        f"  Current : return {cur_ret * 100:+.1f}%  vol {cur_vol * 100:.1f}%  Sharpe {cur_sharpe:.2f}",
        f"  Target  : return {tgt_ret * 100:+.1f}%  vol {tgt_vol * 100:.1f}%  Sharpe {tgt_sharpe:.2f}",
        "",
    ]

    ticker_w, sector_w = _report_column_widths(tickers, sectors)

    lines.append("[bold]Holdings — current → target weight[/bold]")
    hdr = (
        f"  {'Ticker':<{ticker_w}s} {'Sector':<{sector_w}s}  "
        f"{'Current':>8s}   {'Target':>8s}  {'':2s}  {'Est return':>10s}"
    )
    lines.append(f"[dim]{hdr}[/dim]")
    for t, sec, cw, tw, er in zip(
        tickers, sectors, current_weights, target_weights, expected_returns, strict=True
    ):
        delta = (tw - cw) * 100
        arrow = "[green]↑[/green]" if delta > 1 else "[red]↓[/red]" if delta < -1 else "[dim]→[/dim]"
        sec_display = (sec[:sector_w] if len(sec) > sector_w else sec).ljust(sector_w)
        lines.append(
            f"  {t:<{ticker_w}s} [dim]{sec_display}[/dim]  "
            f"{cw * 100:6.1f}% → {tw * 100:6.1f}%  {arrow}  "
            f"[dim]{er * 100:+6.1f}%[/dim]"
        )

    lines.append("")
    lines.append("[bold]Sector exposure (target)[/bold]")
    sector_totals: dict[str, float] = {}
    for sec, tw in zip(sectors, target_weights, strict=False):
        sector_totals[sec] = sector_totals.get(sec, 0.0) + tw
    for sec, wt in sorted(sector_totals.items(), key=lambda x: -x[1]):
        sec_display = (sec[:sector_w] if len(sec) > sector_w else sec).ljust(sector_w)
        bar = "█" * int(wt * 40)
        lines.append(f"  {sec_display} {wt * 100:6.1f}%  {bar}")

    if total_value > 0:
        lines.append("")
        lines.append(f"[bold]Suggested trades[/bold] [dim](portfolio ≈ ${total_value:,.0f})[/dim]")
        trade_hdr = (
            f"  {'Action':<6s} {'Ticker':<{ticker_w}s}  "
            f"{'Shares':>12s}  {'Notional':>12s}"
        )
        lines.append(f"[dim]{trade_hdr}[/dim]")
        for t, q, p, cw, tw in zip(
            tickers, quantities, prices, current_weights, target_weights, strict=True
        ):
            if not p or p <= 0:
                continue
            cur_val = q * p
            tgt_val = total_value * tw
            diff_d = tgt_val - cur_val
            diff_s = diff_d / p
            if abs(diff_d) < total_value * 0.01:
                continue
            action = "Buy" if diff_d > 0 else "Sell"
            color = "green" if diff_d > 0 else "red"
            row = (
                f"  {action:<6s} {t:<{ticker_w}s}  "
                f"{abs(diff_s):>12.4f} sh  ${abs(diff_d):>11,.0f}"
            )
            lines.append(f"[{color}]{row}[/{color}]")

    lines.append("")
    lines.append(
        "[dim]This is mean-variance guidance, not advice. "
        "Past returns and analyst targets are uncertain. "
        "Review tax, liquidity, and conviction before trading.[/dim]"
    )
    return "\n".join(lines)


def run_portfolio_optimization(
    holdings: list[PositionInput],
    *,
    risk_level: int = 5,
    candidate_tickers: list[str] | None = None,
    data_registry=None,
) -> str:
    """Optimize from real positions; optional extra tickers enter at 0% current weight."""
    np = _import_numpy()
    if np is None:
        return "[yellow]numpy is required. Install: pip install numpy[/yellow]"

    config = risk_config(risk_level)
    by_ticker: dict[str, PositionInput] = {}
    for h in holdings:
        by_ticker[h.ticker.upper()] = h
    for t in candidate_tickers or []:
        sym = t.upper()
        if sym not in by_ticker:
            by_ticker[sym] = PositionInput(ticker=sym, quantity=0.0, cost_basis=0.0)

    if len(by_ticker) < 2:
        return (
            "[yellow]Need at least 2 tickers. Add positions with "
            "[white]/portfolio add[/white] or pass tickers: "
            "[white]/optimize risk 5 AAPL,MSFT,NVDA[/white][/yellow]"
        )

    positions = fetch_position_metadata(list(by_ticker.values()), data_registry)
    tickers = [p.ticker for p in positions]

    mu_hist, cov, usable, err = fetch_return_matrix(tickers)
    if err:
        return f"[yellow]{err}[/yellow]"

    pos_by_ticker = {p.ticker: p for p in positions}
    positions = [pos_by_ticker[t] for t in usable if t in pos_by_ticker]
    tickers = usable

    mu_hist_arr = np.array(mu_hist, dtype=float)
    cov_sub = np.array(cov, dtype=float)
    expected = estimate_expected_returns(tickers, mu_hist_arr, data_registry)
    sectors = [p.sector for p in positions]
    prices = [p.price for p in positions]
    quantities = [p.quantity for p in positions]

    values = [q * (p or 0.0) for q, p in zip(quantities, prices, strict=False)]
    total = sum(values)
    if total > 0:
        current_w = [v / total for v in values]
    else:
        current_w = [1.0 / len(tickers)] * len(tickers)

    target_w, opt_err = solve_optimal_weights(expected, cov_sub, sectors, config)
    if opt_err:
        return f"[yellow]{opt_err}[/yellow]"

    return format_optimization_report(
        tickers,
        sectors,
        quantities,
        prices,
        current_w,
        target_w,
        expected,
        np.array(expected, dtype=float),
        cov_sub,
        config,
    )


def holdings_from_storage(storage, portfolio_name: str = "default") -> list[PositionInput]:
    rows = storage.portfolio_list(portfolio_name) if storage else []
    return [
        PositionInput(
            ticker=str(r["ticker"]).upper(),
            quantity=float(r.get("quantity") or 0),
            cost_basis=float(r.get("cost_basis") or 0),
        )
        for r in rows
        if r.get("ticker")
    ]
