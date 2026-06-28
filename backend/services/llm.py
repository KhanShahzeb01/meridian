import httpx
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def chat_completion(
    messages: list[dict],
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
        return _demo_response(messages, system_prompt)

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://meridian-finance.app",
                "X-Title": "Meridian Finance",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": full_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _demo_response(messages: list[dict], system_prompt: Optional[str] = None) -> str:
    """Fallback when no API key is configured."""
    last_msg = messages[-1]["content"] if messages else ""
    persona = "analyst"
    if system_prompt and "Buffett" in system_prompt:
        persona = "Warren Buffett"
    elif system_prompt and "Munger" in system_prompt:
        persona = "Charlie Munger"
    elif system_prompt and "Wood" in system_prompt:
        persona = "Cathie Wood"
    elif system_prompt and "Simons" in system_prompt:
        persona = "Jim Simons"
    elif system_prompt and "Lynch" in system_prompt:
        persona = "Peter Lynch"
    elif system_prompt and "Dalio" in system_prompt:
        persona = "Ray Dalio"
    elif system_prompt and "Chief Investment Officer" in system_prompt:
        persona = "CIO Manager"

    return f"""**[{persona} — Demo Mode]**

> Configure `OPENROUTER_API_KEY` in backend `.env` for live AI analysis.

Based on the query and available market data, here is my analysis:

**Rating:** HOLD (Demo)
**Confidence:** Medium

**Key Points:**
- Fundamental metrics suggest a mixed picture requiring deeper due diligence
- Current valuation appears within historical ranges for the sector
- Monitor upcoming earnings and macro conditions

**Risks:** Market volatility, sector rotation, regulatory changes
**Opportunities:** Potential upside if growth targets are met

---
*Query received: {last_msg[:200]}{'...' if len(last_msg) > 200 else ''}*"""


async def analyze_with_persona(
    ticker: str,
    stock_data: dict,
    persona_prompt: str,
    command_context: str = "",
) -> str:
    data_summary = _format_stock_data(stock_data)
    user_message = f"""Analyze {ticker.upper()} with the following market data:

{data_summary}

{command_context}

Provide your analysis including:
1. Investment thesis (bull and bear cases)
2. Key metrics that matter to your investing style
3. Rating: BUY / HOLD / SELL
4. Price target or fair value estimate if applicable
5. Key risks and catalysts"""

    return await chat_completion(
        messages=[{"role": "user", "content": user_message}],
        system_prompt=persona_prompt,
    )


def _format_stock_data(data: dict) -> str:
    if isinstance(data, dict) and "price" in data:
        lines = [
            f"Company: {data.get('name', 'N/A')}",
            f"Price: ${data.get('price', 'N/A')}",
            f"Change: {data.get('change_pct', 'N/A')}%",
            f"Market Cap: {_format_number(data.get('market_cap'))}",
            f"P/E Ratio: {data.get('pe_ratio', 'N/A')}",
            f"EPS: {data.get('eps', 'N/A')}",
            f"52W High/Low: ${data.get('fifty_two_week_high', 'N/A')} / ${data.get('fifty_two_week_low', 'N/A')}",
            f"Sector: {data.get('sector', 'N/A')}",
            f"Beta: {data.get('beta', 'N/A')}",
        ]
        return "\n".join(lines)
    return str(data)[:3000]


def _format_number(n) -> str:
    if n is None:
        return "N/A"
    if n >= 1e12:
        return f"${n/1e12:.2f}T"
    if n >= 1e9:
        return f"${n/1e9:.2f}B"
    if n >= 1e6:
        return f"${n/1e6:.2f}M"
    return f"${n:,.0f}"
