---
name: fred-economic-data
description: FRED macroeconomic data for GDP, unemployment, inflation, interest rates, and Fed indicators. Use for macro outlook, rates, CPI, recession risk, and tying stock thesis to the economic cycle. Requires FRED_API_KEY for live series (same as /macro).
---

# FRED Economic Data (Rallies)

## Rallies execution — use these tools (not raw Python)

1. **`load_skill`** `fred-economic-data` (this file)
2. **`macro_snapshot`** — no arguments; returns Fed funds, CPI, unemployment, 10Y, GDP (same engine as `/macro`)
3. Optional: **`research_fetch`** with `intent: "macro economy rates inflation"` and any ticker (macro bucket ignores ticker-specific need)
4. For a **stock + macro** question: also **`research_fetch`** quote/financials for the ticker
5. **`web_fetch`** only for a specific FRED series page if user gives a URL

**Do not** invent series values. Cite only tool output. If FRED unavailable, say so and mention `FRED_API_KEY`.

Slash shortcut: user can run `/macro` outside `/research`.

## API key

Set `FRED_API_KEY` (free at https://fred.stlouisfed.org/docs/api/api_key.html).

## Interpretation checklist

- [ ] State latest Fed funds, CPI trend, unemployment, 10Y yield from `macro_snapshot`
- [ ] Link macro regime to the user's question (rates → growth vs value, inflation → margins, etc.)
- [ ] Note data dates on every figure
- [ ] Flag if FRED key missing or series unavailable

## Common FRED series (reference)

| Series | Meaning |
|--------|---------|
| FEDFUNDS | Effective federal funds rate |
| CPIAUCSL | Consumer Price Index |
| UNRATE | Unemployment rate |
| DGS10 | 10-year Treasury yield |
| GDPC1 | Real GDP |

## Output format

1. **Macro snapshot** — bullet latest indicators with dates
2. **Implications** — 2–4 bullets for equities / sectors relevant to the query
3. **Caveats** — revision risk, single-point vs trend
