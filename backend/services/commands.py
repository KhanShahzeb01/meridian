import re
from typing import Optional
from services.yahoo import (
    get_quote,
    get_financials,
    get_news,
    get_filings,
    get_dcf_data,
    screen_stocks,
)
from services.llm import analyze_with_persona, chat_completion
from services.personas import PERSONAS, MANAGER_PROMPT


COMMANDS = {
    "/help": "Show available commands",
    "/quote": "Get real-time stock quote — /quote AAPL",
    "/financials": "View financial statements — /financials MSFT",
    "/news": "Latest news — /news NVDA",
    "/dcf": "DCF valuation analysis — /dcf GOOGL",
    "/filings": "SEC filings (10-K, 10-Q) — /filings TSLA",
    "/consensus": "All personas analyze + vote — /consensus AAPL",
    "/watchlist": "Manage watchlist — /watchlist add AAPL",
    "/portfolio": "Manage portfolio — /portfolio add MSFT 100 350.50",
    "/screener": "Stock screener — /screener sector=Technology max_pe=30",
    "/analyze": "AI analysis with current persona — /analyze AMZN",
    "/clear": "Clear terminal output",
}


def parse_command(text: str) -> tuple[str, list[str], dict]:
    text = text.strip()
    if not text.startswith("/"):
        return "chat", [text], {}

    parts = text.split()
    cmd = parts[0].lower()
    args = parts[1:]

    params = {}
    filtered_args = []
    for arg in args:
        if "=" in arg:
            key, val = arg.split("=", 1)
            params[key] = val
        else:
            filtered_args.append(arg)

    return cmd, filtered_args, params


async def execute_command(
    text: str,
    persona_id: str = "buffett",
) -> dict:
    cmd, args, params = parse_command(text)

    if cmd == "/help":
        return {"type": "help", "content": _format_help()}

    if cmd == "/clear":
        return {"type": "clear", "content": ""}

    if cmd == "/quote":
        ticker = args[0] if args else None
        if not ticker:
            return {"type": "error", "content": "Usage: /quote TICKER"}
        try:
            data = get_quote(ticker)
            return {"type": "quote", "content": _format_quote(data), "data": data}
        except Exception as e:
            return {"type": "error", "content": f"Failed to fetch quote: {e}"}

    if cmd == "/financials":
        ticker = args[0] if args else None
        if not ticker:
            return {"type": "error", "content": "Usage: /financials TICKER"}
        try:
            data = get_financials(ticker)
            return {"type": "financials", "content": _format_financials(data), "data": data}
        except Exception as e:
            return {"type": "error", "content": f"Failed to fetch financials: {e}"}

    if cmd == "/news":
        ticker = args[0] if args else None
        if not ticker:
            return {"type": "error", "content": "Usage: /news TICKER"}
        try:
            news = get_news(ticker)
            return {"type": "news", "content": _format_news(ticker, news), "data": news}
        except Exception as e:
            return {"type": "error", "content": f"Failed to fetch news: {e}"}

    if cmd == "/dcf":
        ticker = args[0] if args else None
        if not ticker:
            return {"type": "error", "content": "Usage: /dcf TICKER"}
        try:
            data = get_dcf_data(ticker)
            persona = PERSONAS.get(persona_id, PERSONAS["buffett"])
            analysis = await analyze_with_persona(
                ticker,
                get_quote(ticker),
                persona["system_prompt"],
                f"Perform a DCF valuation analysis. DCF data: {data}",
            )
            return {
                "type": "dcf",
                "content": f"## DCF Analysis — {ticker.upper()}\n\n{_format_dcf_summary(data)}\n\n---\n\n{analysis}",
                "data": data,
            }
        except Exception as e:
            return {"type": "error", "content": f"DCF analysis failed: {e}"}

    if cmd == "/filings":
        ticker = args[0] if args else None
        if not ticker:
            return {"type": "error", "content": "Usage: /filings TICKER"}
        try:
            data = get_filings(ticker)
            return {"type": "filings", "content": _format_filings(data), "data": data}
        except Exception as e:
            return {"type": "error", "content": f"Failed to fetch filings: {e}"}

    if cmd == "/analyze":
        ticker = args[0] if args else None
        if not ticker:
            return {"type": "error", "content": "Usage: /analyze TICKER"}
        try:
            quote = get_quote(ticker)
            persona = PERSONAS.get(persona_id, PERSONAS["buffett"])
            analysis = await analyze_with_persona(ticker, quote, persona["system_prompt"])
            return {
                "type": "analysis",
                "content": analysis,
                "persona": persona["name"],
                "data": quote,
            }
        except Exception as e:
            return {"type": "error", "content": f"Analysis failed: {e}"}

    if cmd == "/consensus":
        ticker = args[0] if args else None
        if not ticker:
            return {"type": "error", "content": "Usage: /consensus TICKER"}
        try:
            return await _run_consensus(ticker)
        except Exception as e:
            return {"type": "error", "content": f"Consensus analysis failed: {e}"}

    if cmd == "/screener":
        try:
            results = screen_stocks(
                sector=params.get("sector"),
                min_market_cap=float(params["min_market_cap"]) if params.get("min_market_cap") else None,
                max_pe=float(params["max_pe"]) if params.get("max_pe") else None,
                min_dividend_yield=float(params["min_div"]) if params.get("min_div") else None,
            )
            return {"type": "screener", "content": _format_screener(results), "data": results}
        except Exception as e:
            return {"type": "error", "content": f"Screener failed: {e}"}

    if cmd == "/watchlist":
        action = args[0] if args else "show"
        ticker = args[1] if len(args) > 1 else None
        return {
            "type": "watchlist",
            "action": action,
            "ticker": ticker,
            "content": f"Watchlist command: {action}" + (f" {ticker}" if ticker else ""),
        }

    if cmd == "/portfolio":
        action = args[0] if args else "show"
        return {
            "type": "portfolio",
            "action": action,
            "args": args[1:],
            "content": f"Portfolio command: {action}",
        }

    if cmd == "chat":
        persona = PERSONAS.get(persona_id, PERSONAS["buffett"])
        ticker_match = re.search(r"\b([A-Z]{1,5})\b", args[0] if args else "")
        stock_context = ""
        if ticker_match:
            try:
                stock_context = str(get_quote(ticker_match.group(1)))
            except Exception:
                pass
        response = await chat_completion(
            messages=[{"role": "user", "content": args[0] if args else text}],
            system_prompt=persona["system_prompt"] + f"\n\nStock context if relevant: {stock_context}",
        )
        return {"type": "chat", "content": response, "persona": persona["name"]}

    return {"type": "error", "content": f"Unknown command: {cmd}. Type /help for available commands."}


async def _run_consensus(ticker: str) -> dict:
    quote = get_quote(ticker)
    analyses = []

    for pid, persona in PERSONAS.items():
        analysis = await analyze_with_persona(ticker, quote, persona["system_prompt"])
        analyses.append(f"### {persona['name']}\n{analysis}")

    combined = "\n\n".join(analyses)
    manager_response = await chat_completion(
        messages=[
            {
                "role": "user",
                "content": f"Synthesize these analyst opinions on {ticker.upper()}:\n\n{combined}",
            }
        ],
        system_prompt=MANAGER_PROMPT,
        max_tokens=6000,
    )

    return {
        "type": "consensus",
        "content": f"# Consensus Analysis — {ticker.upper()}\n\n## Individual Analyses\n\n{combined}\n\n---\n\n## Manager Summary\n\n{manager_response}",
        "data": {"ticker": ticker, "analyses_count": len(PERSONAS)},
    }


def _format_help() -> str:
    lines = ["## Available Commands\n"]
    for cmd, desc in COMMANDS.items():
        lines.append(f"`{cmd}` — {desc}")
    lines.append("\n**Personas:** Warren Buffett, Charlie Munger, Cathie Wood, Jim Simons, Peter Lynch, Ray Dalio")
    lines.append("\nSelect a persona from the panel to change analysis perspective.")
    return "\n".join(lines)


def _format_quote(d: dict) -> str:
    sign = "+" if (d.get("change") or 0) >= 0 else ""
    return f"""## {d['name']} ({d['ticker']})

| Metric | Value |
|--------|-------|
| Price | **${d['price']}** ({sign}{d.get('change_pct', 0)}%) |
| Open | ${d.get('open', 'N/A')} |
| Day Range | ${d.get('low', 'N/A')} — ${d.get('high', 'N/A')} |
| 52W Range | ${d.get('fifty_two_week_low', 'N/A')} — ${d.get('fifty_two_week_high', 'N/A')} |
| Market Cap | {_fmt_cap(d.get('market_cap'))} |
| P/E Ratio | {d.get('pe_ratio', 'N/A')} |
| EPS | ${d.get('eps', 'N/A')} |
| Dividend Yield | {_fmt_pct(d.get('dividend_yield'))} |
| Beta | {d.get('beta', 'N/A')} |
| Sector | {d.get('sector', 'N/A')} |
| Volume | {_fmt_vol(d.get('volume'))} |"""


def _format_financials(d: dict) -> str:
    m = d.get("key_metrics", {})
    return f"""## Financials — {d['name']} ({d['ticker']})

### Key Metrics
| Metric | Value |
|--------|-------|
| Revenue | {_fmt_cap(m.get('revenue'))} |
| Gross Profit | {_fmt_cap(m.get('gross_profit'))} |
| Operating Income | {_fmt_cap(m.get('operating_income'))} |
| Net Income | {_fmt_cap(m.get('net_income'))} |
| Total Debt | {_fmt_cap(m.get('total_debt'))} |
| Total Cash | {_fmt_cap(m.get('total_cash'))} |
| Free Cash Flow | {_fmt_cap(m.get('free_cash_flow'))} |
| ROE | {_fmt_pct(m.get('roe'))} |
| ROA | {_fmt_pct(m.get('roa'))} |
| Profit Margin | {_fmt_pct(m.get('profit_margin'))} |"""


def _format_news(ticker: str, news: list) -> str:
    if not news:
        return f"No recent news found for {ticker.upper()}."
    lines = [f"## Latest News — {ticker.upper()}\n"]
    for i, item in enumerate(news, 1):
        lines.append(f"**{i}. {item['title']}**")
        lines.append(f"   *{item.get('publisher', 'Unknown')}* — {item.get('published', '')[:10]}")
        if item.get("link"):
            lines.append(f"   [{item['link'][:60]}...]({item['link']})")
        lines.append("")
    return "\n".join(lines)


def _format_filings(d: dict) -> str:
    filings = d.get("filings", [])
    if not filings:
        return f"No SEC filings found for {d['ticker']}."
    lines = [f"## SEC Filings — {d['ticker']}\n"]
    for f in filings:
        lines.append(f"- **{f.get('type', 'Filing')}** ({f.get('date', 'N/A')}) — {f.get('title', '')}")
        if f.get("url"):
            lines.append(f"  [View on EDGAR]({f['url']})")
    return "\n".join(lines)


def _format_dcf_summary(d: dict) -> str:
    fcf_lines = "\n".join(f"  - {f['year']}: {_fmt_cap(f['fcf'])}" for f in d.get("fcf_history", []))
    return f"""### Valuation Inputs
| Metric | Value |
|--------|-------|
| Current Price | ${d.get('current_price', 'N/A')} |
| Market Cap | {_fmt_cap(d.get('market_cap'))} |
| Enterprise Value | {_fmt_cap(d.get('enterprise_value'))} |
| EV/EBITDA | {d.get('ev_to_ebitda', 'N/A')} |
| P/E Ratio | {d.get('pe_ratio', 'N/A')} |
| PEG Ratio | {d.get('peg_ratio', 'N/A')} |
| Analyst Target | ${d.get('analyst_target', 'N/A')} |
| Recommendation | {d.get('recommendation', 'N/A')} |

### FCF History
{fcf_lines or '  No FCF history available'}"""


def _format_screener(results: list) -> str:
    if not results:
        return "No stocks matched your screener criteria."
    lines = ["## Stock Screener Results\n"]
    lines.append("| Ticker | Price | Change | P/E | Market Cap | Sector |")
    lines.append("|--------|-------|--------|-----|------------|--------|")
    for s in results[:20]:
        sign = "+" if (s.get("change_pct") or 0) >= 0 else ""
        lines.append(
            f"| {s['ticker']} | ${s.get('price', 'N/A')} | {sign}{s.get('change_pct', 0)}% "
            f"| {s.get('pe_ratio', 'N/A')} | {_fmt_cap(s.get('market_cap'))} | {s.get('sector', 'N/A')} |"
        )
    return "\n".join(lines)


def _fmt_cap(n) -> str:
    if n is None:
        return "N/A"
    if abs(n) >= 1e12:
        return f"${n/1e12:.2f}T"
    if abs(n) >= 1e9:
        return f"${n/1e9:.2f}B"
    if abs(n) >= 1e6:
        return f"${n/1e6:.2f}M"
    return f"${n:,.0f}"


def _fmt_pct(n) -> str:
    if n is None:
        return "N/A"
    return f"{n*100:.2f}%" if abs(n) < 1 else f"{n:.2f}%"


def _fmt_vol(n) -> str:
    if n is None:
        return "N/A"
    if n >= 1e9:
        return f"{n/1e9:.2f}B"
    if n >= 1e6:
        return f"{n/1e6:.2f}M"
    return f"{n:,.0f}"
