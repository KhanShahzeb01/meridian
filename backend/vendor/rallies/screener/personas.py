import json

from ..metric_units import SCREENER_UNIT_LEGEND, format_decimal_as_pct, format_pct_value

VALUE_SYSTEM = """You are a **Value Investor** (Benjamin Graham / Warren Buffett style).
Your philosophy: buy stocks trading below their intrinsic worth with a margin of safety.

You focus on:
- Low P/E (trailing and forward) — lower is better
- Low P/B — lower is better
- Low P/S — lower is better
- Low PEG — ideally under 1.0
- Low debt-to-equity
- Meaningful dividend yield (>1.5% is a bonus)
- Consistent earnings with no major losses
- Free cash flow generation

Score each stock 1-10 where:
- 1-3: Overvalued / no value case
- 4-5: Fairly valued / average
- 6-7: Undervalued / good value
- 8-10: Deep value / strong margin of safety

Return a JSON array. No markdown, no explanation outside the JSON."""

GROWTH_SYSTEM = """You are a **Growth Investor** (Peter Lynch / high-momentum style).
Your philosophy: find companies compounding revenue and earnings at above-average rates.

You focus on:
- Revenue growth rate — higher and accelerating is best
- Earnings growth rate — EPS compounding >15% ideally
- Expanding gross margins — pricing power indicator
- Expanding operating margins — operating leverage
- High ROIC — efficient capital deployment
- PEG ratio — growth at reasonable price (PEG < 2 is attractive)
- Strong forward guidance / analyst upgrades

Score each stock 1-10 where:
- 1-3: No growth / declining
- 4-5: Moderate growth / market average
- 6-7: Solid growth / attractive
- 8-10: Exceptional growth / market leader

Return a JSON array. No markdown, no explanation outside the JSON."""

QUALITY_SYSTEM = """You are a **Quality Investor** (Joel Greenblatt / O'Shaughnessy style).
Your philosophy: buy high-quality businesses with durable competitive advantages.

You focus on:
- High ROE (>15%) — efficient use of equity
- High ROIC (>10%) — efficient capital allocation
- Low debt-to-equity (< 1.0) — financial safety
- High and stable gross margins — pricing power
- High and stable operating margins — operational efficiency
- Consistent profitability (no loss years)
- Strong free cash flow generation
- Low beta — less volatility

Score each stock 1-10 where:
- 1-3: Poor quality / high risk
- 4-5: Average quality / acceptable
- 6-7: Good quality / above average
- 8-10: Excellent quality / best-in-class

Return a JSON array. No markdown, no explanation outside the JSON."""

MOMENTUM_SYSTEM = """You are a **Momentum / Technical Investor** (quant / trend-following style).
Your philosophy: buy stocks with strong price momentum and institutional accumulation.

You focus on:
- Recent price performance — 3-month and 12-month returns
- Stock trading near its 52-week high (within 10%) is bullish
- Volume above average — confirms institutional interest
- Low volatility / beta not too high
- Price above key moving averages implies upward trend
- Positive earnings surprises drive momentum
- Strong analyst ratings and price targets with upside

Score each stock 1-10 where:
- 1-3: Weak momentum / downtrend
- 4-5: Neutral / sideways
- 6-7: Good momentum / uptrend
- 8-10: Strong momentum / market leader

Return a JSON array. No markdown, no explanation outside the JSON."""

MODERATOR_SYSTEM = """You are a **Debate Moderator** for a stock screening panel.
Four specialist agents (Value, Growth, Quality, Momentum) have each scored the same set of stocks and provided their reasoning.

Your job:
1. For each stock that appeared in any agent's list, note the consensus and any disagreements
2. Write a 1-2 sentence thesis for the top 10 stocks
3. Flag stocks where agents strongly disagree (high conviction on both sides)
4. Return a final ranked list

Return a JSON object:
{
  "ranked": [
    {"ticker": "NVDA", "avg_score": 8.5, "consensus": "Strong buy", "thesis": "..."},
    ...
  ],
  "flagged_disagreements": [
    {"ticker": "TSLA", "value": 3, "growth": 9, "note": "Value says overvalued, Growth says compounding — buyer beware"}
  ]
}

No markdown, no extra text."""

PERSONAS: dict[str, dict] = {
    "value": {
        "name": "Value Investor",
        "system": VALUE_SYSTEM,
        "short": "Value",
    },
    "growth": {
        "name": "Growth Investor",
        "system": GROWTH_SYSTEM,
        "short": "Growth",
    },
    "quality": {
        "name": "Quality Investor",
        "system": QUALITY_SYSTEM,
        "short": "Quality",
    },
    "momentum": {
        "name": "Momentum Investor",
        "system": MOMENTUM_SYSTEM,
        "short": "Momentum",
    },
}


def build_screener_prompt(persona_key: str, criteria_text: str, data_rows: list[dict]) -> list[dict]:
    p = PERSONAS.get(persona_key)
    if p is None:
        raise ValueError(f"Unknown persona: {persona_key}")

    compact = _format_data_table(data_rows)

    criteria_note = ""
    if criteria_text:
        criteria_note = f"\nUser screening criteria: {criteria_text}\nWeight these in your scoring."

    persona_name = p["name"]
    suffix = f" for {persona_name} criteria" if not criteria_text else ""
    user_prompt = (
        f"Screen these {len(data_rows)} stocks{suffix}."
        f"{criteria_note}"
        f"\n\nData:\n{compact}"
        f"\n\n{SCREENER_UNIT_LEGEND}"
        f"\n\nReturn a JSON array of objects with keys: ticker (str), score (int 1-10), reasoning (str, max 15 words)."
        f"\nScore only the stocks that meet your criteria. You may return fewer than {len(data_rows)}."
        f"\nSort by score descending."
    )

    return [
        {"role": "system", "content": p["system"]},
        {"role": "user", "content": user_prompt},
    ]


def build_moderator_prompt(
    criteria_text: str,
    all_results: dict[str, dict[str, dict]],
    total_candidates: int,
) -> list[dict]:
    sections = []
    for agent_key, scores in all_results.items():
        p = PERSONAS.get(agent_key, {})
        name = p.get("name", agent_key)
        lines = [f"--- {name} ---"]
        for ticker, info in sorted(scores.items(), key=lambda x: x[1].get("score", 0), reverse=True)[:15]:
            lines.append(f"  {ticker}: {info.get('score', '?')}/10 — {info.get('reasoning', '')}")
        sections.append("\n".join(lines))

    return [
        {"role": "system", "content": MODERATOR_SYSTEM},
        {"role": "user", "content": (
            f"Review {total_candidates} stocks scored by 4 agents.\n"
            f"User criteria: {criteria_text}\n\n"
            + "\n\n".join(sections)
            + "\n\nReturn final ranked JSON with thesis for the top stocks."
        )},
    ]


def _format_value(v) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, float):
        if abs(v) >= 1e12:
            return f"${v/1e12:.2f}T"
        if abs(v) >= 1e9:
            return f"${v/1e9:.1f}B"
        if abs(v) >= 1e6:
            return f"${v/1e6:.0f}M"
        if abs(v) >= 1000:
            return f"{v:,.0f}"
        if abs(v) < 1:
            return f"{v:.2f}"
        return f"{v:.1f}"
    return str(v)


def _format_data_table(rows: list[dict]) -> str:
    header = (
        "Ticker   Price$  P/E   FwdPE  P/B    P/S    RevGr%  Margin%  ROE%   D/E    Mom3M%   MktCap$"
    )
    sep = "-------  ------  ----  -----  ----   ----   ------  -------  ----   ----   ------   -------"
    lines = [header, sep]
    for r in rows:
        price = _fmt(r.get("price"))
        pe = _fmt(r.get("pe"))
        fpe = _fmt(r.get("forward_pe"))
        pb = _fmt(r.get("pb"))
        ps = _fmt(r.get("ps"))
        rg = format_decimal_as_pct(r.get("rev_growth"))
        mg = format_decimal_as_pct(r.get("profit_margin"))
        roe = format_decimal_as_pct(r.get("roe"))
        de_val = _fmt(r.get("de"))
        mom3 = format_pct_value(r.get("mom_3m_pct"))
        mcap = _fmt_mcap(r.get("mcap"))
        ticker = str(r.get("ticker", ""))[:6].ljust(6)
        parts = [
            ticker.center(0),
            price.rjust(6),
            pe.rjust(4),
            fpe.rjust(5),
            pb.rjust(5),
            ps.rjust(4),
            rg.rjust(5),
            mg.rjust(5),
            roe.rjust(4),
            de_val.rjust(5),
            mom3.rjust(6),
            mcap.rjust(7),
        ]
        lines.append("  ".join(parts))
    return "\n".join(lines)


def _fmt(v: object) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, float):
        if abs(v) >= 1e12:
            return f"${v/1e12:.2f}T"
        if abs(v) >= 1e9:
            return f"${v/1e9:.1f}B"
        if abs(v) >= 1e6:
            return f"${v/1e6:.0f}M"
        if abs(v) >= 1000:
            return f"{v:,.0f}"
        if abs(v) < 1:
            return f"{v:.2f}"
        return f"{v:.1f}"
    return str(v)


def _fmt_mcap(v: object) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, (int, float)):
        if v >= 1e12:
            return f"${v/1e12:.2f}T"
        if v >= 1e9:
            return f"${v/1e9:.1f}B"
        if v >= 1e6:
            return f"${v/1e6:.0f}M"
        return str(v)
    return str(v)
