---
name: hedgefundmonitor
description: OFR Hedge Fund Monitor — Form PF leverage, industry AUM, repo volumes, systemic risk. Use for hedge fund leverage, financial stability, counterparty/repo stress, and macro risk backdrop. No API key required.
---

# OFR Hedge Fund Monitor (Rallies)

## Rallies execution — use these tools (not raw HTTP in-chat)

1. **`load_skill`** `hedgefundmonitor` (this file)
2. **`hedgefund_snapshot`** — no arguments; latest OFR series (same engine as `/hedgefund`)
3. Optional: **`macro_snapshot`** when linking HF leverage to rates/macro
4. For **single-stock** questions: also **`research_fetch`** quote/financials — HF data is **industry-level**, not per ticker

Slash shortcut: `/hedgefund`.

**Do not** invent leverage or AUM figures. Cite only `hedgefund_snapshot` output.

## Datasets (reference)

| Dataset | Content |
|---------|---------|
| fpf | SEC Form PF — hedge fund aggregates |
| ficc | Sponsored repo volumes |
| tff | CFTC financial futures positioning |
| scoos | Dealer financing terms (survey) |

## Workflow

```
- [ ] load_skill hedgefundmonitor
- [ ] hedgefund_snapshot()
- [ ] Interpret leverage, GAV/NAV, repo vs prior period in output
- [ ] Tie to user question (systemic risk, risk-on/risk-off, credit conditions)
- [ ] Optional macro_snapshot for rates/CPI context
```

## Key metrics in snapshot

- HF Leverage (avg) — `FPF-ALLQHF_LEVERAGERATIO_GAVWMEAN`
- Gross / Net Assets — industry totals
- Sponsored Repo Volume — `FICC-SPONSORED_REPO_VOL`

## Output format

1. **Industry snapshot** — table or bullets from tool with dates
2. **Trend** — vs prior period when tool provides `previous`
3. **Market implications** — liquidity, crowding, tail risk (qualitative, grounded in data)
4. **Limits** — quarterly lag, aggregates only, not fund-specific 13F
