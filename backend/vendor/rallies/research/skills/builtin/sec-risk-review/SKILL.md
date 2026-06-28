---
name: sec-risk-review
description: Deep read of SEC risk disclosures for one ticker. Use for risk factors, regulatory risks, 10-K risks, what could go wrong, downside scenarios from filings.
---

# SEC Risk Review Skill (Rallies)

Sources risks **from the company's own filings** via edgartools — not generic LLM risk lists.

## Required tool sequence

1. **`filing_section`** — `{ticker, section: "risk factors"}` — full Item 1A (may be truncated; note in output)
2. **`filing_section`** — `{ticker, section: "business"}` — context for what they do
3. **`research_fetch`** — `{ticker, intent: "news"}` — recent events that activate specific risks
4. Optional: **`research_fetch`** — `{ticker, intent: "insider"}` — selling into risk window

## Output format

1. **Top 5 material risks** — paraphrase from Item 1A with filing date; quote key phrases sparingly
2. **Risk → tripwire map** — for each risk, one observable metric or event that confirms it
3. **New vs last year** — if excerpt shows major themes (AI, regulation, concentration), call them out
4. **Not in filing** — separate section for market risks *not* disclosed (label as analyst inference)

## Do not

- List generic macro risks without filing support
- Use Financial Datasets — `filing_section` only
