---
name: earnings-digest
description: Pre-earnings or post-earnings briefing for one ticker. Use for earnings preview, earnings recap, beat miss, guidance, quarterly results.
---

# Earnings Digest Skill (Rallies)

Quick structured briefing before or after an earnings print.

## Required tool sequence

1. **`gather_equity_bundle`** — `{ticker}` — financials, news, SEC recent filings
2. **`research_fetch`** — `{ticker, intent: "financials"}` — trailing revenue/EPS trends
3. **`filing_section`** — `{ticker, section: "MD&A"}` — management commentary from latest 10-Q/K
4. **`research_fetch`** — `{ticker, intent: "news"}` — recent headlines (guidance, previews)

## Output sections

1. **Setup** — report date if known from news; last quarter revenue/EPS from financials
2. **What matters** — 3 KPIs to watch (company-specific, from MD&A or news)
3. **Whisper / consensus** — only if present in news tool output; else "consensus not in free sources"
4. **Bull / bear into print** — one paragraph each, tied to data
5. **Post-print checklist** — what to verify in 8-K / press release (margin, guide, FCF)

## Do not

- Fabricate consensus EPS — rallies free stack has no FD estimates
- Skip `gather_equity_bundle` — it anchors the whole digest
