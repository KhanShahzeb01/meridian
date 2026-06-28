---
name: dcf-valuation
description: Full DCF workflow using rallies /dcf quant engine plus live Yahoo data. Use for fair value, intrinsic value, price target, undervalued/overvalued questions.
---

# DCF Valuation Skill (Rallies)

Runs the **same quant engine as `/dcf`** — this skill adds data gathering, WACC discipline, sensitivity, and validation.

## Required tool sequence

1. **`gather_equity_bundle`** — quote, financials, margins (validates FCF context)
2. **`run_dcf_quant`** — `{ticker, growth_rate?, wacc?}` — deterministic fair value
3. Optional second **`run_dcf_quant`** with WACC ±1% for sensitivity cross-check
4. **`research_fetch`** with intent `quote` — current price for upside/downside

## WACC by sector

Use [sector-wacc.md](sector-wacc.md) for base WACC bands before calling `run_dcf_quant`.

Default if sector unknown: growth 10%, WACC 9%, terminal growth 3% (matches `/dcf` defaults).

## Workflow

```
- [ ] gather_equity_bundle(TICKER)
- [ ] Pick growth + WACC from sector table and FCF history
- [ ] run_dcf_quant(TICKER, growth_rate, wacc)
- [ ] 3×3 sensitivity narrative (WACC ±1%, terminal growth 2%/2.5%/3%)
- [ ] Compare fair value vs live quote; state margin of safety
- [ ] Caveats: terminal value weight, cyclical FCF, one-time items
```

## Output format

1. **Valuation summary** — fair value, price, upside/downside %
2. **Assumptions table** — growth, WACC, terminal growth (cite `/dcf` output)
3. **Sensitivity** — at least a 3×3 grid or three WACC scenarios
4. **Sanity checks** — FCF positive? EV plausible vs market cap?
5. **Caveats** — standard DCF limits + company-specific risks from bundle

## Do not

- Invent FCF or price — use `run_dcf_quant` and `research_fetch`
- Replace `/dcf` for a quick number — use `/dcf TICKER` directly instead
