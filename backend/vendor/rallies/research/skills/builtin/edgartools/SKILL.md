---
name: edgartools
description: SEC EDGAR filings via rallies edgartools integration — 10-K, 10-Q, 8-K, risk factors, MD&A, business description, insider Form 4. Use for filing text, regulatory narrative, and fundamentals from primary sources.
---

# SEC EDGAR / edgartools (Rallies)

## Rallies execution — use these tools (not the Python edgar library in-chat)

1. **`load_skill`** `edgartools` (this file)
2. **`filing_section`** — `{ticker, section}` e.g. risk factors, MD&A, business (NL section query)
3. **`gather_equity_bundle`** — quote, financials, news, insider, SEC excerpts in one call
4. **`research_fetch`** with `intent: "sec filing 10-K risk"` or `insider` / `financials` as needed
5. For compare: **`research_fetch_multi`** per ticker with filing or financials intent

Slash shortcuts: `/filing TICKER section`, `/sec TICKER`, `/insider TICKER`, `/financials TICKER`.

**Do not** invent filing text. Quote or paraphrase only from tool results.

## Workflow

```
- [ ] load_skill edgartools
- [ ] gather_equity_bundle(TICKER) for context
- [ ] filing_section(TICKER, "risk factors") for 10-K risks
- [ ] filing_section(TICKER, "MD&A") for management discussion
- [ ] Optional: research_fetch insider / financials
- [ ] Synthesize with dates and form types cited
```

## Section routing hints

| User asks | filing_section query |
|-----------|---------------------|
| Annual risks | risk factors (10-K) |
| Quarterly trends | MD&A (10-Q) |
| Business model | business description |
| Recent events | 8-K items (via bundle / sec list) |

## Output format

1. **Filing context** — form, filing date, section sourced
2. **Key excerpts** — bullets with material facts (numbers when present)
3. **Investment takeaway** — what changed vs prior narrative
4. **Limits** — edgartools coverage, truncated sections, no XBRL tables unless in tool output

## Pitfalls

- Do not claim `filing.financials` — use `gather_equity_bundle` or `research_fetch` financials
- Prefer latest annual for risk factors; quarterly for MD&A trajectory
- Set `EDGAR_IDENTITY` env for SEC compliance when using edgartools backend
