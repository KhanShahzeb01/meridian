# Compound slash commands

Combine **multiple quick commands on one line**. Rallies loads data from **context** commands first, then runs the **primary** command with that data attached.

---

## Activation rules

| Rule | Detail |
|------|--------|
| **Primary first** | The line must **start** with a slash command (that token is the primary). |
| **At least two commands** | There must be **another** `/command` later on the same line. |
| **Execution order** | Context steps run by **priority** (not left-to-right in your sentence), then the primary. |
| **Cleaned prompt** | Embedded `/watchlist`, `/portfolio`, etc. are **removed** from the text sent to the primary; your question stays. |
| **Named lists** | Optional name right after `/watchlist` or `/portfolio` selects that list; the name is stripped from the cleaned prompt too. |

**Not compound:** a single command (`/ask munger NVDA`), or text before the first `/` (`please /ask …`).

---

## Execution order (context priority)

When several context commands appear on one line, they always run in this order:

```
/watchlist → /portfolio → /quote → /financials → … → PRIMARY
```

Example — same result either way:

```text
/ask munger pick 5 from my /watchlist and /portfolio
/ask munger pick 5 from my /portfolio and /watchlist
```

Both run: watchlist → portfolio → ask.

Named lists in compound (each `/watchlist` or `/portfolio` step uses the name **immediately after** that token):

```text
/ask munger compare /watchlist watchlist_khan /portfolio portfolio_2025
/research rebalance /portfolio portfolio_2025
/ask dalio macro /watchlist watchlist_finance /portfolio portfolio_khan
```

Omit the name to use the **default** watchlist or **default** portfolio (same as bare `/watchlist` or `/portfolio`).

**Natural-language words are not list names.** Tokens like `holdings`, `optimize`, `rebalance`, and `positions` after `/portfolio` or `/watchlist` are ignored — the **default** list is used. Unknown names (e.g. a typo) fall back to `default` with a dim note. Empty lists still attach a context block so `/ask` and `/research` see “no positions” instead of failing silently.

---

## Named watchlists & portfolios (compound + single)

You can maintain **multiple** named lists. In compound lines, put the list name directly after the slash command (no `add` in the compound string).

| Goal | Compound example |
|------|------------------|
| Named watchlist only | `/research overvalued names /watchlist watchlist_finance` |
| Named portfolio only | `/research rebalance /portfolio portfolio_2025` |
| Both named | `/ask munger … /watchlist watchlist_khan /portfolio portfolio_2025` |
| Default lists | `/ask munger … /watchlist /portfolio` |

**Single-command equivalents** (not compound):

```text
/watchlist watchlist_khan MU          # shorthand add to named watchlist
/watchlist watchlist_finance add NVDA
/portfolio portfolio_2025 add MU 1.5 876
/portfolio portfolios               # list all portfolio names
/watchlist watchlists               # list all watchlist names
```

**Naming:** start with a letter; use letters, numbers, `_`, `-` (e.g. `watchlist_khan`, `portfolio_2025`). Existing tickers were migrated to **`default`**.

---

## Fully supported (v1)

### Primary commands (5)

| Command | Purpose |
|---------|---------|
| `/ask` | Ask one persona (e.g. Munger, Buffett) |
| `/debate` | Two personas debate (`PERSONA_A vs PERSONA_B`) |
| `/research` | Tool loop with live data |
| `/consensus` | Seven-category expert panel + summary (random expert per category, shuffled order) |
| `/memo` | Investment memo pipeline → HTML file |

### Context commands (4) — data is loaded

| Command | Arguments | Provides |
|---------|-----------|----------|
| `/watchlist` | optional `NAME` | Tickers from **default** or **named** watchlist + quote snapshot |
| `/portfolio` | optional `NAME` | Holdings from **default** or **named** portfolio + position values (USD) |
| `/quote` | `TICKER` immediately after | One ticker quote block |
| `/financials` | `TICKER` immediately after | One ticker financials block |

Examples:

```text
/watchlist                          → default watchlist
/watchlist watchlist_khan           → named watchlist only
/portfolio portfolio_2025           → named portfolio only
```

### Ticker scope

- **Watchlist / portfolio:** no artificial cap — every ticker in the **selected** list is in scope and in the snapshot.
- **`/ask`, `/debate`, `/research`, `/memo`:** use the **full** compound ticker list.
- **Standalone `/ask`** (no compound): still capped at **5** tickers inferred from question text only.
- **`/consensus`:** analyzes **all** watchlist/portfolio tickers in **batches of 6** (seven experts + batch summary per batch), then a **master table** with price, verdict, and thesis for every name. Each run picks a **random** persona from each of the seven categories (not the same seven names every time).

---

## `/optimize` (standalone, not compound primary)

Portfolio rebalance is a **system** command, not a compound primary. Use it after you have holdings:

```text
/optimize risk 5
/optimize risk 7
/portfolio list
/portfolio portfolio_2025 add MU 1.5 876
```

Risk dial **1** = conservative (tighter caps) · **10** = aggressive. The word `risk` is required (`/optimize 7` alone is not parsed as risk level). Watchlist tickers can be merged into the optimization universe. Output uses fixed-width **Holdings** and **Suggested trades** tables.

For narrative rebalance advice with persona context, use compound **`/ask`** or **`/research`** with **`/portfolio`**, not `/optimize` alone.

---

## All working patterns (75 shapes)

**5 primaries** × **15 non-empty subsets** of the four wired context types.

### One context (20 examples)

**`/ask`**

```text
/ask munger pick the best 5 from my /watchlist
/ask buffett which names look expensive /watchlist watchlist_finance
/ask buffett trim losers /portfolio portfolio_2025
/ask buffett which names look expensive /portfolio
/ask dalio is /quote NVDA still reasonable
/ask munger compare growth vs value on /financials MSFT
```

**`/debate`**

```text
/debate buffett vs lynch is tech overowned /watchlist
/debate dalio vs wood macro view on /portfolio
/debate buffett vs munger /quote AAPL
/debate lynch vs buffett /financials GOOG
```

**`/research`**

```text
/research which watchlist names have deteriorating margins /watchlist
/research which names look weak /watchlist watchlist_khan
/research position sizing vs current holdings /portfolio
/research rebalance my holdings /portfolio portfolio_2025
/research latest narrative for /quote TSLA
/research revenue trend /financials AMZN
```

**`/consensus`**

```text
/consensus /watchlist
/consensus /portfolio
/consensus /quote NVDA
/consensus /financials MSFT
```

**`/memo`**

```text
/memo AAPL long competitive moat vs peers /watchlist
/memo MSFT short risks relative to /portfolio
/memo NVDA long /quote NVDA
/memo AAPL long /financials AAPL
```

> `/memo` still requires `TICKER` and `long` or `short` in the cleaned prompt.

### Two contexts (6 pairs × 5 primaries)

| Pair | Example |
|------|---------|
| watchlist + portfolio | `/ask munger … /watchlist /portfolio` |
| named watchlist + named portfolio | `/ask munger … /watchlist watchlist_khan /portfolio portfolio_2025` |
| watchlist + quote | `/ask munger … /watchlist /quote SPY` |
| watchlist + financials | `/research margin trends /watchlist /financials AAPL` |
| portfolio + quote | `/debate buffett vs lynch … /portfolio /quote NVDA` |
| portfolio + financials | `/ask dalio … /portfolio /financials MSFT` |
| quote + financials | `/ask munger … /quote AAPL /financials AAPL` |

### Three contexts (4 triples × 5 primaries)

```text
/ask munger … /watchlist /portfolio /quote SPY
/ask munger … /watchlist /portfolio /financials MSFT
/ask munger … /watchlist /quote NVDA /financials NVDA
/ask munger … /portfolio /quote AAPL /financials AAPL
```

### Four contexts (1 × 5 primaries)

```text
/ask munger rank ideas /watchlist /portfolio /quote SPY /financials MSFT
```

---

## Recognized but not fully wired

### Extra context (compound runs; step skipped with a note)

`/earnings`, `/news`, `/peers`, `/insider`, `/holdings`, `/sec`, `/sector`, `/index`, `/macro`, `/vix`, `/screen`, `/bundle`

```text
/ask munger outlook /watchlist /news
```

→ watchlist loads; `/news` is skipped until a resolver is added.

### Extra primary at line start (yellow “not wired yet”)

`/screen`, `/dcf`, `/optimize`, `/options`, `/analysis`, `/chart`, `/filing`, `/bundle`, `/fetch`, `/skill`

Use a supported primary (`/ask`, `/debate`, `/research`, `/consensus`, `/memo`) at the start instead.

---

## What does **not** work

| Pattern | Why |
|---------|-----|
| `/watchlist` then `/ask …` | Primary must be **first** — use `/ask … /watchlist` |
| `/ask NVDA` only | Need a **second** `/command` on the line |
| `/help /watchlist` | System/meta first token → not treated as compound |
| `/quote` without ticker | Put ticker right after: `/quote AAPL` |
| `/debate a b question` | Debate needs `vs`: `/debate a vs b question` |
| `/portfolio add MU` in compound | Use `/portfolio portfolio_2025` — `add` forms are **system** commands, not context |
| `/watchlist add NVDA` in compound | Use `/watchlist watchlist_khan` or bare `/watchlist` for default |

---

## Quick reference

| Goal | Command |
|------|---------|
| Persona ranks entire watchlist | `/ask munger pick the best 5 from my /watchlist` |
| Persona ranks **named** watchlist | `/ask munger pick best /watchlist watchlist_khan` |
| Debate using holdings | `/debate buffett vs dalio trim losers? /portfolio` |
| Research on **named** portfolio | `/research rebalance /portfolio portfolio_2025` |
| Research over watchlist | `/research which names look overvalued /watchlist` |
| Panel on watchlist | `/consensus /watchlist` |
| Optimize holdings (quant) | `/optimize risk 5` (after `/portfolio add …`) |
| Persona + portfolio context | `/ask munger optimize and rebalance /portfolio` |
| Memo with list context | `/memo AAPL long vs industry /watchlist` |
| Multi-source question | `/ask lynch … /portfolio /watchlist /quote SPY` |
| Named watchlist + named portfolio | `/research … /watchlist watchlist_finance /portfolio portfolio_khan` |

---

## Tips

1. Put the **action** first (`/ask`, `/research`, …) and **data sources** anywhere after (`/watchlist`, `/portfolio`, …).
2. For a **specific** list, put its name right after the command: `/watchlist watchlist_khan`, `/portfolio portfolio_2025`.
3. Wording can be natural: “from my `/watchlist`” uses the **default** list; use `/watchlist watchlist_khan` for a named list.
4. For ranking or comparing **many** tickers, prefer **`/ask`** or **`/research`** over **`/consensus`** (panel cost).
5. Manage lists outside compound: `/watchlist watchlists`, `/portfolio portfolios`, and `add`/`remove` on each list.
6. Type **`/compound_help`** anytime to show this guide again.
