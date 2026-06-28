---
name: compare-equities
description: Side-by-side comparison of 2–5 tickers on valuation and fundamentals. Use for compare, versus, vs, which is better, margins, growth, or peer analysis.
---

# Compare Equities Skill (Rallies)

Structured peer comparison using **live data only** — no training-data multiples.

## Required tool sequence

1. **`research_fetch_multi`** — `{tickers: [...], intent: "financials and margins"}`
2. **`research_fetch_multi`** — `{tickers: [...], intent: "quote"}` (if not in step 1)
3. Optional: **`research_fetch_multi`** — `{tickers: [...], intent: "news"}` for catalyst context
4. Optional per ticker: **`filing_section`** — `{section: "risk factors"}` when comparing risk profiles

## Analysis framework

For each ticker, extract from tool output:

| Metric | Source |
|--------|--------|
| Price, P/E, market cap | quote |
| Revenue, net income trends | financials |
| Gross / operating / net margin | margins rows |
| Recent news / catalysts | news |

## Output format

1. **Comparison table** — tickers as columns, metrics as rows (markdown table)
2. **Ranked view** — best/worst on 2–3 dimensions user asked about
3. **Trade-offs** — why one name wins on X but loses on Y
4. **Data date** — cite filing periods from tool output

## Example queries

- "compare AAPL and MSFT margins" → step 1 with intent `margins`
- "CRM vs NOW vs WDAY growth" → step 1 with intent `financials and revenue growth`

## Do not

- Answer from memory — always call `research_fetch_multi` first
- Compare more than 5 tickers — cap at 5
