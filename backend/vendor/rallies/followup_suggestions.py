"""Context-aware follow-up question suggestions after quick slash commands."""

from __future__ import annotations

import re
from collections.abc import Sequence

from rich.panel import Panel

_MAX_QUESTIONS = 3
_MIN_QUESTIONS = 1

_SCREEN_STYLE_HINTS = {
    "momentum": "Which screen winners have the strongest price momentum?",
    "value": "Which picks look most undervalued on fundamentals?",
    "growth": "Which screen winners have the best revenue growth?",
    "quality": "Which picks score highest on profitability and balance sheet quality?",
    "dividend": "Which dividend picks offer the best yield and payout safety?",
}


def _first_ticker(tickers: Sequence[str] | None) -> str | None:
    if not tickers:
        return None
    for sym in tickers:
        text = str(sym or "").strip().upper()
        if text:
            return text
    return None


def _join_tickers(tickers: Sequence[str] | None, *, limit: int = 3) -> str:
    if not tickers:
        return ""
    names = [str(t).strip().upper() for t in tickers if str(t or "").strip()]
    if not names:
        return ""
    if len(names) <= limit:
        return ", ".join(names)
    return ", ".join(names[:limit]) + "…"


def _screen_criteria(user_prompt: str | None) -> str:
    text = str(user_prompt or "").strip()
    if text.lower().startswith("/screen"):
        text = text[len("/screen") :].strip()
    return text or "this screen"


def _screen_style_question(criteria: str) -> str:
    lowered = criteria.lower()
    for style, question in _SCREEN_STYLE_HINTS.items():
        if style in lowered:
            return question
    return "Which of these screen picks has the strongest overall thesis?"


def _top_screen_tickers(screen_text: str | None, *, limit: int = 3) -> list[str]:
    if not screen_text:
        return []
    from .ticker_identify import identify_session_tickers

    return identify_session_tickers(screen_text)[:limit]


def build_followup_questions(
    command: str,
    *,
    tickers: Sequence[str] | None = None,
    persona_name: str | None = None,
    persona_a: str | None = None,
    persona_b: str | None = None,
    user_prompt: str | None = None,
    screen_text: str | None = None,
) -> list[str]:
    """
    Return 1–3 plain-English follow-up questions for a completed quick command.

    Questions are meant to be typed as-is on the next turn (no slash prefix).
    """
    cmd = str(command or "").strip().lower()
    questions: list[str] = []

    if cmd == "/screen":
        criteria = _screen_criteria(user_prompt)
        top = _top_screen_tickers(screen_text)
        top_label = _join_tickers(top) or "the top picks"
        questions.append(
            "Analyze stocks scored above 7 from this screen in more detail"
        )
        questions.append(f"Compare the top 3 picks from this screen ({top_label})")
        questions.append(_screen_style_question(criteria))

    elif cmd == "/ask":
        who = persona_name or "this persona"
        ticker = _first_ticker(tickers)
        questions.append(f"Research {who}'s opinion in more detail")
        if ticker:
            questions.append(
                f"What would {who} say is the biggest risk for {ticker}?"
            )
        questions.append(f"How does {who}'s view compare to the consensus panel?")

    elif cmd == "/debate":
        a = persona_a or "the first expert"
        b = persona_b or "the second expert"
        ticker = _first_ticker(tickers)
        questions.append("Which side made the stronger argument and why?")
        questions.append(f"Summarize where {a} and {b} agree and disagree")
        if ticker:
            questions.append(
                f"What would tip the scale for a buy decision on {ticker}?"
            )
        else:
            questions.append("What evidence would change your mind on this debate?")

    elif cmd == "/consensus":
        joined = _join_tickers(tickers)
        questions.append("Research the value investor's opinion in more detail")
        if len(tickers or []) == 1 and joined:
            questions.append(
                f"What are the biggest risks the panel flagged for {joined}?"
            )
        elif joined:
            questions.append(
                f"Which of {joined} had the strongest bull case from the panel?"
            )
        else:
            questions.append(
                "Which ticker had the strongest bull case from the panel?"
            )
        if joined:
            questions.append(f"Compare the highest-rated tickers ({joined}) side by side")
        else:
            questions.append("Compare the highest-rated tickers side by side")

    else:
        questions.append("Dig deeper into this result in plain English")

    cleaned: list[str] = []
    for q in questions:
        line = re.sub(r"\s+", " ", str(q or "").strip())
        if line and line not in cleaned:
            cleaned.append(line)

    if not cleaned:
        cleaned.append("Dig deeper into this result in plain English")

    return cleaned[:_MAX_QUESTIONS] if len(cleaned) >= _MIN_QUESTIONS else cleaned


def print_followup_questions_panel(console, questions: Sequence[str]) -> None:
    """Render suggested follow-ups in a green bordered panel."""
    lines = [str(q).strip() for q in questions if str(q or "").strip()]
    if not lines:
        lines = ["Dig deeper into this result in plain English"]
    body = "\n".join(lines[:_MAX_QUESTIONS])
    console.print(Panel(body, title="Follow-up questions", border_style="green"))
