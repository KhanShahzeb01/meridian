"""Cross-turn REPL memory: LangGraph turn pairs or legacy conversation list."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .helpers import TokenCounter
from .ticker_identify import (
    identify_query_tickers,
    sanitize_ticker_list,
    session_focus_tickers,
    tickers_from_conversation,
)
from .ticker_library import extract_dollar_tickers
from .token_budgets import default_thread_token_budget

DEFAULT_MAX_THREAD_TOKENS = default_thread_token_budget()

# Prior assistant replies can be huge (compare tables); trim for JSON planner only.
PLANNER_PRIOR_ASSISTANT_MAX_CHARS = 4000

_PLANNER_PLAN_PREFIX_RE = re.compile(r"^\s*\[\s*\{", re.DOTALL)

_COMPARE_HINT_RE = re.compile(
    r"\b(compare|comparison|versus|vs\.?|side[\s-]by[\s-]side|which has better|rank)\b",
    re.IGNORECASE,
)
_SUMMARY_HINT_RE = re.compile(
    r"\b("
    r"conclusion|summary|summarize|final|recommend|allocation|allocate|"
    r"distribute|distribution|split|portfolio|how much|how should i"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResolvedTurn:
    """How the current prompt should be interpreted given prior thread."""

    raw_prompt: str
    effective_prompt: str
    active_tickers: tuple[str, ...]
    is_follow_up: bool
    prior_turn_count: int
    prior_command: str | None = None


def _turn_pair_memory_enabled() -> bool:
    from .graph.flags import turn_pair_memory_enabled

    return turn_pair_memory_enabled()


def _load_turn_pair_messages(session_id: str | None) -> list[dict]:
    from .memory.file_store import load_session_llm_messages

    if not session_id:
        return []
    return load_session_llm_messages(session_id)


def session_messages(
    conversation: list[dict],
    *,
    session_id: str | None = None,
) -> list[dict]:
    """
    Cross-turn messages for follow-up resolution and LLM context.

    When LangGraph turn-pair memory is on, loads persisted query/answer pairs
    only (no planner steps). Falls back to the in-memory REPL list when the
    store is empty (e.g. first turn or path mismatch).
    """
    in_memory = [m for m in conversation if m.get("role") in ("user", "assistant")]
    if _turn_pair_memory_enabled() and session_id:
        stored = _load_turn_pair_messages(session_id)
        if stored:
            return stored
        # File may exist with only the in-flight human line — use REPL list.
        if in_memory:
            return in_memory
    return in_memory


def session_tickers_from_text(text: str) -> list[str]:
    """Strict ticker extraction for a single message (session mode)."""
    from .ticker_identify import identify_session_tickers

    return identify_session_tickers(text)


def should_inject_compare_prefetch(*, raw_prompt: str, is_follow_up: bool) -> bool:
    """
    Whether to append the forced side-by-side compare instruction at answer time.

    Skip on follow-ups that ask for conclusions, allocation, or recommendations.
    """
    text = (raw_prompt or "").strip()
    if not text:
        return False
    if not is_follow_up:
        return True
    if _SUMMARY_HINT_RE.search(text):
        return False
    if _COMPARE_HINT_RE.search(text):
        return True
    return False


def prior_thread_messages(
    conversation: list[dict],
    current_prompt: str,
    *,
    session_id: str | None = None,
) -> list[dict]:
    """Thread history before the in-flight user message for this turn."""
    prior = list(session_messages(conversation, session_id=session_id))
    if (
        prior
        and prior[-1].get("role") == "user"
        and str(prior[-1].get("content") or "").strip() == current_prompt.strip()
    ):
        prior = prior[:-1]
    return [m for m in prior if m.get("role") in ("user", "assistant")]


def _last_slash_command(prior: list[dict]) -> str | None:
    """Most recent slash command in prior user messages (e.g. /screen)."""
    for msg in reversed(prior):
        if msg.get("role") != "user":
            continue
        content = str(msg.get("content") or "").strip()
        if content.startswith("/"):
            return content.split(None, 1)[0].lower()
    return None


def _last_assistant_content(prior: list[dict]) -> str:
    for msg in reversed(prior):
        if msg.get("role") == "assistant":
            return str(msg.get("content") or "")
    return ""


def resolve_follow_up(
    conversation: list[dict],
    current_prompt: str,
    *,
    session_id: str | None = None,
) -> ResolvedTurn:
    """
    Link vague follow-ups to prior session context (tickers, topic).

    Uses LangGraph turn pairs when enabled — only raw user queries and final
    answers, never planner steps or sub-step tool output.
    """
    prior = prior_thread_messages(
        conversation, current_prompt, session_id=session_id
    )
    active = tickers_from_conversation(prior)
    current_dollar = extract_dollar_tickers(current_prompt)
    current_other = sanitize_ticker_list(
        [
            sym
            for sym in identify_query_tickers(current_prompt)
            if sym not in current_dollar
        ]
    )

    slash_command = current_prompt.strip().startswith("/")
    if current_dollar:
        merged = sanitize_ticker_list(list(dict.fromkeys(current_dollar)))
        is_follow_up = False
    elif slash_command:
        merged = sanitize_ticker_list(current_other)
        is_follow_up = False
    else:
        merged = sanitize_ticker_list(list(dict.fromkeys(active + current_other)))
        is_follow_up = bool(prior) and bool(merged)

    prior_command = _last_slash_command(prior)
    session_tickers = merged
    if is_follow_up:
        if prior_command:
            from .ticker_identify import tickers_from_last_assistant

            screen_tickers = tickers_from_last_assistant(prior)
            if screen_tickers:
                session_tickers = screen_tickers
            else:
                focus = session_focus_tickers(prior, merged)
                if focus:
                    session_tickers = focus
        else:
            focus = session_focus_tickers(prior, merged)
            if focus:
                session_tickers = focus

    # LangGraph-style memory: prior user/assistant pairs carry context; do not
    # inject a synthetic follow-up blob into the user message.
    effective = current_prompt.strip()

    return ResolvedTurn(
        raw_prompt=current_prompt.strip(),
        effective_prompt=effective,
        active_tickers=tuple(session_tickers[:5]),
        is_follow_up=is_follow_up,
        prior_turn_count=len([m for m in prior if m.get("role") == "user"]),
        prior_command=prior_command,
    )


def prior_context_for_llm(
    conversation: list[dict],
    current_prompt: str,
    *,
    session_id: str | None = None,
    max_tokens: int = DEFAULT_MAX_THREAD_TOKENS,
) -> list[dict]:
    """
    Prior completed user/assistant pairs for follow-up turns (free-form prompts).

    Slash commands (/ask, /consensus, /screen, …) run in isolation and only
    *write* turns to memory; they do not call this. Excludes the in-flight user
    line for current_prompt.
    """
    prior = prior_thread_messages(
        conversation, current_prompt, session_id=session_id
    )
    return trim_thread_to_budget(prior, max_tokens)


def trim_thread_to_budget(messages: list[dict], max_tokens: int) -> list[dict]:
    """Drop oldest turns until the clean thread fits the token budget."""
    counter = TokenCounter()
    trimmed = [m for m in messages if m.get("role") in ("user", "assistant")]
    while len(trimmed) > 1 and counter.count_conversation_tokens(trimmed) > max_tokens:
        trimmed.pop(0)
        if trimmed and trimmed[0].get("role") == "assistant":
            trimmed.pop(0)
    return trimmed


def _trim_assistant_for_planner(content: str, max_chars: int) -> str:
    text = str(content or "")
    if len(text) <= max_chars:
        return text
    return (
        text[:max_chars]
        + "\n\n...[prior answer truncated for planner context]..."
    )


def _is_within_turn_planner_artifact(message: dict) -> bool:
    if message.get("role") != "assistant":
        return False
    content = str(message.get("content") or "")
    return bool(_PLANNER_PLAN_PREFIX_RE.match(content))


def messages_for_planner(
    workspace: list[dict],
    current_raw_prompt: str,
    *,
    prior_command: str | None = None,
    prior_assistant_max_chars: int = PLANNER_PRIOR_ASSISTANT_MAX_CHARS,
) -> list[dict]:
    """
    Cross-turn chat memory for the JSON planner.

    Default: prior **user** queries plus the current question.

    After a slash command (/screen, /consensus, …), also include a trimmed copy
    of the latest assistant answer so the planner can use that output instead of
    re-fetching unrelated external data.

    Stops before within-turn plan steps and tool data blocks.
    """
    current_raw_prompt = str(current_raw_prompt or "").strip()
    cutoff = len(workspace)
    for index in range(len(workspace) - 1, -1, -1):
        message = workspace[index]
        if message.get("role") != "user" or message.get("type") == "data":
            continue
        if str(message.get("content") or "").strip() == current_raw_prompt:
            cutoff = index + 1
            break

    prior_assistant_excerpt = ""
    if prior_command:
        for message in reversed(workspace[:cutoff]):
            if message.get("role") != "assistant":
                continue
            if message.get("type") == "data":
                continue
            if _is_within_turn_planner_artifact(message):
                continue
            prior_assistant_excerpt = _trim_assistant_for_planner(
                str(message.get("content") or ""),
                prior_assistant_max_chars,
            )
            break

    out: list[dict] = []
    inserted_prior_assistant = False
    for message in workspace[:cutoff]:
        role = message.get("role")
        if role != "user":
            continue
        if message.get("type") == "data":
            continue
        if _is_within_turn_planner_artifact(message):
            break
        content = str(message.get("content") or "")
        out.append({"role": role, "content": content})
        if (
            prior_command
            and not inserted_prior_assistant
            and prior_assistant_excerpt.strip()
            and content.strip().lower().startswith(prior_command)
        ):
            out.append(
                {"role": "assistant", "content": prior_assistant_excerpt}
            )
            inserted_prior_assistant = True

    if prior_command and prior_assistant_excerpt.strip() and not inserted_prior_assistant:
        out.insert(
            max(len(out) - 1, 0),
            {"role": "assistant", "content": prior_assistant_excerpt},
        )

    return out


def build_thread_context(
    conversation: list[dict],
    *,
    raw_prompt: str,
    effective_prompt: str,
    max_tokens: int = DEFAULT_MAX_THREAD_TOKENS,
    session_id: str | None = None,
) -> list[dict]:
    """
    Cross-turn messages for this turn: trimmed prior user/assistant pairs +
    the current user query (raw text only — like LangGraph add_messages).

    Within-turn planner steps and tool output are appended to workspace later
    but are not part of cross-turn memory.
    """
    del effective_prompt  # retained for call-site compatibility
    prior = prior_thread_messages(
        conversation, raw_prompt, session_id=session_id
    )
    thread = trim_thread_to_budget(prior, max_tokens)
    thread.append({"role": "user", "content": raw_prompt.strip()})
    return thread


def new_turn_workspace(
    conversation: list[dict],
    *,
    raw_prompt: str,
    effective_prompt: str,
    max_tokens: int = DEFAULT_MAX_THREAD_TOKENS,
    session_id: str | None = None,
) -> list[dict]:
    """Ephemeral workspace for within-turn planner steps (not stored in thread)."""
    return build_thread_context(
        conversation,
        raw_prompt=raw_prompt,
        effective_prompt=effective_prompt,
        max_tokens=max_tokens,
        session_id=session_id,
    )


def record_assistant_turn(
    conversation: list[dict],
    answer_text: str,
    *,
    raw_user_query: str | None = None,
    session_id: str | None = None,
) -> None:
    """
    Persist the final assistant reply for cross-turn memory.

    LangGraph mode: append one user_query + assistant_answer pair (raw query only).
    Legacy mode: append assistant message to the REPL conversation list.
    """
    text = str(answer_text or "").strip()
    if not text:
        return

    if _turn_pair_memory_enabled() and session_id:
        from .memory.file_store import append_assistant_answer

        append_assistant_answer(session_id, text)

    conversation.append({"role": "assistant", "content": text})


def record_command_turn(
    conversation: list[dict],
    *,
    user_query: str,
    assistant_answer: str,
    session_id: str | None = None,
) -> None:
    """
    Record a completed slash-command turn for later follow-ups.

    Commands do not read this back into their own LLM calls; free-form prompts do.
    """
    user_line = str(user_query or "").strip()
    answer = str(assistant_answer or "").strip()
    if not user_line or not answer:
        return
    if not any(
        str(m.get("content") or "").strip() == user_line and m.get("role") == "user"
        for m in conversation
    ):
        conversation.append({"role": "user", "content": user_line})
    if _turn_pair_memory_enabled() and session_id:
        from .memory.file_store import append_user_query

        append_user_query(session_id, user_line)
    record_assistant_turn(
        conversation,
        answer,
        raw_user_query=user_line,
        session_id=session_id,
    )


def hydrate_conversation_from_session(
    conversation: list[dict],
    *,
    session_id: str | None = None,
) -> int:
    """
    Load persisted user/assistant pairs into the REPL list on startup.

    Returns the number of messages hydrated (0 if none or list already populated).
    """
    if conversation:
        return 0
    stored = session_messages(conversation, session_id=session_id)
    if not stored:
        return 0
    conversation.extend(stored)
    return len(stored)


def record_user_query(
    user_query: str,
    *,
    session_id: str | None = None,
) -> None:
    """Persist the user's question at turn start (before planning/answer)."""
    if not _turn_pair_memory_enabled() or not session_id:
        return
    from .memory.file_store import append_user_query

    append_user_query(session_id, user_query)


def clear_session_memory(
    conversation: list[dict],
    *,
    session_id: str | None = None,
) -> None:
    """Clear REPL conversation and LangGraph turn-pair store."""
    conversation.clear()
    if _turn_pair_memory_enabled() and session_id:
        from .memory.file_store import clear_session_memory_file

        clear_session_memory_file(session_id)
