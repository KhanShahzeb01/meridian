"""Single-shot chat for general conversation — no rallies planner loop."""

from __future__ import annotations

import re
from typing import Any

from rallies.llm import LLMError
from rallies.quotes import format_yfinance_quote_line
from rallies.sources.registry import extract_tickers

from services.fast_llm import fast_prompt
from services.market_data import finnhub_quote_dict

SYSTEM_PROMPT = """You are Meridian Finance, a concise financial research assistant.
Answer clearly in markdown when helpful. Keep responses focused.
Use only live market data provided in the conversation context.
Never invent stock prices, dates, or financial figures.
If live data is missing, say it is unavailable — do not guess."""

_GREETING = re.compile(
    r"^(hi|hey|hello|howdy|yo|sup|thanks|thank you|ok|okay|bye|good morning|good afternoon)[!.?\s]*$",
    re.I,
)


_TICKER_WORD = re.compile(r"\b([A-Z]{1,5})\b")


def _tickers_in_text(text: str) -> list[str]:
    tickers = list(extract_tickers(text) or [])
    if tickers:
        return tickers
    # Fallback: bare uppercase symbols in questions like "what is AAPL trading at?"
    stop = {"I", "A", "THE", "AND", "OR", "FOR", "AT", "IS", "IT", "TO", "OF", "ON", "IN", "VS"}
    found: list[str] = []
    for m in _TICKER_WORD.finditer(text):
        sym = m.group(1)
        if sym not in stop and sym not in found:
            found.append(sym)
    return found[:3]


def _prefetch_block(manager: Any, prompt: str) -> str:
    tickers = _tickers_in_text(prompt)
    if not tickers:
        return ""

    yfs = manager.data_registry.get_source("yfinance") if manager.data_registry else None
    lines: list[str] = []
    for ticker in tickers[:3]:
        data = yfs.get_quote(ticker) if yfs else finnhub_quote_dict(ticker)
        if data and not data.get("error"):
            lines.append(format_yfinance_quote_line(data))
    if not lines:
        return ""
    return (
        "## Live market data (authoritative — use these exact figures)\n"
        + "\n".join(lines)
        + "\n\nDo not invent prices. If a metric is missing above, say unavailable."
    )


def _history_messages(conversation: list) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for msg in conversation[-6:]:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content.strip()})
    return out


def run_fast_chat(prompt: str, conversation: list, manager: Any) -> str:
    """One LLM call with optional quote prefetch — Plexus-style speed."""
    text = prompt.strip()
    if not text:
        return ""

    if _GREETING.match(text):
        return (
            "Hi — I'm Meridian Finance. Ask about any ticker (`$AAPL`), "
            "use slash commands like `/quote AAPL`, or type `/help` for the full menu."
        )

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(_history_messages(conversation))

    data_block = _prefetch_block(manager, text)
    if data_block:
        messages.append({"role": "user", "content": data_block})

    messages.append({"role": "user", "content": text})

    answer = fast_prompt(manager.agent.llm, messages, task_type="answer")
    if not answer:
        raise LLMError("Model returned an empty response.", reason_code="empty_response")

    conversation.append({"role": "user", "content": text})
    conversation.append({"role": "assistant", "content": answer})
    return answer
