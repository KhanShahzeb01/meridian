# Valuation charts (P/E, EPS, PEG)

Research-backed chart types used by `/chart` in rallies-cli. Trailing panels use four-quarter EPS and adjusted prices from **yfinance** (live, no chart cache). Forward analyst fields appear in summary / compare snapshots, not on single-ticker time-series panels A–E.

## Metrics

| Metric | Definition | Typical use |
|--------|------------|-------------|
| **EPS (trailing)** | Sum of last four reported quarters | Earnings power today |
| **P/E** | Price ÷ trailing EPS | How much you pay per $1 of earnings |
| **PEG** | P/E ÷ EPS growth rate (%) | Peter Lynch: ~1.0 “fair” when growth supports the multiple |
| **Earnings yield** | 1 ÷ P/E (or EPS ÷ price) | Compare to bonds / alternatives |

**PEG rule of thumb (Lynch):** PEG &lt; 1 often looks cheap vs growth; &gt; 2 expensive. Use **consistent** growth: trailing YoY for the PEG time series; **~5y EPS CAGR** on the scatter panel (less noisy than single-quarter YoY).

## Single ticker — `/chart TICKER [horizon]`

| Panel | What it shows |
|-------|----------------|
| Fair value vs price | Price + median P/E × EPS fair line |
| Price vs trailing EPS | Dual axis |
| Trailing P/E | History + percentile band + median |
| Forward vs trailing P/E | Snapshot bar (yfinance) |
| Analyst targets vs price | Low / mean / high vs current |

- Layout: `dashboard_plotly.py` + `plotly_layout.apply_valuation_grid_*`
- HTML: full-viewport responsive + gray banner (`write_responsive_html`)
- Flags: `[ytd|1y|5y|10y|max]`, `--no-llm`

## Multi-ticker — `/chart AAPL MSFT …` (2–5 tickers)

**Chart types** (from `stocks_valuation.ipynb` via `notebook_charts.py`):

| Panel | Type |
|-------|------|
| EPS vs P/E | Scatter; marker size ≈ price; Viridis colorbar = price |
| Forward vs trailing P/E | Scatter + 45° line |
| Analyst targets | Range lines + mean + current price |
| P/E vs EV/EBITDA | Scatter + Burry zone shading; PEG colorbar |

**Layout** (`plotly_layout.py` sector helpers + `write_responsive_html(..., compare=True)`):

- Gray **banner** at top; tickers + horizon in banner (no subtitle band)
- **Full horizontal width**; tall figure; **page scrolls** vertically if needed
- **2×2** equal boxes; **12%** gap between columns; **9%** between rows
- Title in top band of each box; colorbar in **right margin inside** its box
- Terminal: Rich comparison table + optional LLM summary

**Do not** use single-ticker time-series panels for multi-ticker compare.

## Data

- History: `build_pe_frame` → `slice_for_horizon`
- Compare snapshots: `compare.snapshot_from_series` + `build_market_snapshot`
- LLM: `facts.py` → `llm_summary.py` (structured JSON only)

## Tests

`tests/test_charts.py`, `tests/test_chart_dashboard.py`, `tests/test_notebook_charts.py`

## References

- Peter Lynch PEG; historical P/E bands; notebook: `stocks_valuation/stocks_valuation.ipynb`
