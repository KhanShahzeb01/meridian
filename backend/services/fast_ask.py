"""Fast path for persona /ask — one LLM call, no research session."""

from __future__ import annotations

import re
from typing import Any

from rallies.advanced.personas import PERSONAS
from rallies.llm import LLMError
from rallies.sources.registry import extract_tickers

from services.fast_chat import _prefetch_block, _history_messages
from services.fast_llm import fast_prompt


def _parse_ask(routed: str) -> tuple[str, str] | None:
    parts = routed.strip().split(maxsplit=2)
    if len(parts) < 3 or not parts[0].lower().startswith("/ask"):
        return None
    persona_key = parts[1].lower()
    question = parts[2].strip()
    if persona_key not in PERSONAS or not question:
        return None
    return persona_key, question


def run_fast_ask(routed: str, conversation: list, manager: Any) -> str:
    parsed = _parse_ask(routed)
    if not parsed:
        raise ValueError("Invalid /ask")

    persona_key, question = parsed
    persona = PERSONAS[persona_key]
    name = persona.get("name", persona_key)
    style = persona.get("style", "")
    quote = persona.get("quote", "")

    system = (
        f"You are {name}, responding in the voice and analytical style of this investor.\n"
        f"Style: {style}\n"
        f'Known for: "{quote}"\n\n'
        "Answer in clear markdown. Be concise (under 350 words).\n"
        "Use only live market data provided below — never invent prices or figures.\n"
        "If data is missing, say unavailable."
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(_history_messages(conversation)[-6:])

    data_block = _prefetch_block(manager, question)
    if not data_block:
        tickers = extract_tickers(question) or []
        if tickers:
            data_block = _prefetch_block(manager, "$" + tickers[0])
    if data_block:
        messages.append({"role": "user", "content": data_block})

    messages.append({"role": "user", "content": question})

    answer = fast_prompt(manager.agent.llm, messages, task_type="summary")
    if not answer:
        raise LLMError("Model returned an empty response.", reason_code="empty_response")

    conversation.append({"role": "user", "content": routed})
    conversation.append({"role": "assistant", "content": answer})
    return answer
