---
name: write-memo
description: Draft a buyside investment memo (HTML on disk). Triggers for write a memo, investment memo, thesis, pitch, long writeup, short writeup, memo on TICKER.
---

# Write Investment Memo (Rallies)

Produces a **multi-section HTML file** at `.rallies/memos/TICKER_LONG_YYYY-MM-DD.html`:

- Key metrics table + embedded price/P/E charts
- Full narrative (thesis, scenarios, catalysts, risks)
- DCF quant output + valuation analysis
- 3-expert panel (Buffett, Lynch, Simons)
- References & data sources

Chat output = header summary + file path only.

## Frame the trade (required)

- **Ticker**, **direction** (LONG/SHORT), **horizon** (default 12mo), **conviction** (high/medium/low)
- **Variant view** — one sentence on what consensus misses (derive from data if user didn't provide)

## Required tool sequence

### Step 1 — Data (parallel OK)

| Tool | Arguments | Purpose |
|------|-----------|---------|
| `gather_equity_bundle` | `{ticker}` | Quote, financials, margins, news, insider, SEC list, business + risk excerpts |
| `filing_section` | `{ticker, section: "MD&A"}` | Recent quarterly trajectory |
| `run_dcf_quant` | `{ticker}` | Base-case valuation anchor (optional for pre-revenue names) |

### Step 2 — Draft content

Fill every slot in `memo-template.html` (read via skill folder reference):

- `variant_view`, `thesis_bullets` (3–5 falsifiable bullets with *Wrong if …*)
- `business_snapshot`, `whats_priced_in`
- Bear / Base / Bull scenarios → `scenario_table`, narratives, probability weights sum to 100%
- `catalysts_table`, `risks_table` (each risk needs an **observable tripwire**)
- `position_management`, `monitoring_kpis`

Style rules: first person plural ("we"), no AI filler words, numbers on every claim, steelman the bear case.

### Step 3 — Write file

Call **`write_memo_html`**:

```json
{
  "ticker": "AAPL",
  "direction": "LONG",
  "html_content": "<!DOCTYPE html>...full rendered memo..."
}
```

Build HTML by replacing all `{{slot}}` placeholders from the template. Set `{{date}}` to today (YYYY-MM-DD).

### Step 4 — Chat response (only this)

```
[TICKER] · [LONG/SHORT] · Target $X (+Y%) · Asymmetry [N.Nx] · [Conviction]

Memo saved to .rallies/memos/[FILENAME].html
```

Do **not** paste the full memo in chat.

## Self-critique (mandatory before write_memo_html)

1. Variant view contradicts something specific in the data
2. Every thesis bullet has *Wrong if …*
3. Bear narrative ≥ bull narrative strength
4. Asymmetry ≥ 2× or flagged in header
5. No invented consensus — use tool data or say "not available"
