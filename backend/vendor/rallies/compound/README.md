# Compound slash commands

**Status: COMPLETE (2026-06-03+)** — see [SESSION_HANDOFF.md](../../../SESSION_HANDOFF.md).  
**Updates (2026-06):** compound list stopwords, empty portfolio/watchlist context blocks, `/consensus` random panel per category.

**Additive** layer: one line may reference multiple quick commands. Existing
handlers are unchanged; this package runs first from `handle_command`.

## Rules

1. Line must **start** with a slash command (the **primary**).
2. Any other known commands in the same line are **context** (data sources).
3. **Execution order**: all context steps first (by priority), then primary.
4. Text order does not matter for execution — `/ask … /watchlist` still resolves watchlist before Munger runs.

## Example

```
/ask munger to pick 5 stocks from my /watchlist
```

1. Resolve `/watchlist` → tickers + snapshot block  
2. Run `/ask` with cleaned prompt and `manager.compound_context`

**Ticker scope:** `/watchlist` and `/portfolio` resolvers load **every** stored
ticker (no 20-ticker cap). Compound `/ask`, `/debate`, `/research`, and `/memo`
use the full list. Standalone `/ask` still caps at 5 tickers inferred from text
only. `/consensus` on long lists runs in **batches of 6** tickers (seven experts +
batch summary each), then one **master table** for all names; each run **randomly
selects** one persona per category and shuffles order.

**List resolution:** words like `holdings` / `rebalance` after `/portfolio` are not treated as list names; unknown names fall back to `default`.

## Supported (v1)

| Role | Commands |
|------|----------|
| Primary | `/ask`, `/debate`, `/research`, `/consensus`, `/memo` |
| Context | `/watchlist`, `/portfolio`, `/quote TICKER`, `/financials TICKER` |

More context commands can be added in `resolvers/dispatch.py` without touching primary handlers.

User-facing guide: type **`/compound_help`** (loads `COMPOUND_HELP.md` via Rich Markdown).

## Layout

- `parser.py` — find command tokens  
- `ordering.py` — build `ExecutionPlan`  
- `resolvers/` — fetch context data  
- `context_merge.py` — `CompoundContext`  
- `primary_dispatch.py` — call existing handlers  
- `executor.py` — entry `try_handle_compound_command`
