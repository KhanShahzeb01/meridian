"""
File-based session memory — LangGraph-style human/ai message list on disk.

Each CLI session gets one JSON file under .rallies/memory/{session_id}.json.
The file grows after every completed user query + final assistant answer.
Only message *content* is stored and passed to the LLM (no metadata blobs).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..research.paths import session_memory_dir

MEMORY_HUMAN = "human"
MEMORY_AI = "ai"

_HUMAN_TYPES = frozenset({"human", "user", "HumanMessage"})
_AI_TYPES = frozenset({"ai", "assistant", "AIMessage"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_memory_path(session_id: str) -> Path:
    """Path to the JSON memory file for a session."""
    safe_id = str(session_id or "").strip()
    if not safe_id:
        raise ValueError("session_id is required")
    return session_memory_dir() / f"{safe_id}.json"


def _empty_document(session_id: str, *, started_at: str | None = None) -> dict[str, Any]:
    now = started_at or _utc_now()
    return {
        "session_id": session_id,
        "started_at": now,
        "updated_at": now,
        "messages": [],
    }


def _read_document(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _write_document(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def init_session_memory_file(
    session_id: str,
    *,
    started_at: str | None = None,
) -> Path:
    """Create an empty memory file for a new session."""
    session_id = str(session_id or "").strip()
    path = session_memory_path(session_id)
    if path.exists():
        return path
    document = _empty_document(session_id, started_at=started_at)
    _write_document(path, document)
    return path


def ensure_session_memory_file(
    session_id: str,
    *,
    started_at: str | None = None,
) -> Path:
    """Ensure a memory file exists (create if missing)."""
    session_id = str(session_id or "").strip()
    path = session_memory_path(session_id)
    if not path.exists():
        return init_session_memory_file(session_id, started_at=started_at)
    return path


def load_session_memory_file(session_id: str) -> dict[str, Any]:
    """Load raw on-disk document (messages may include type + content only)."""
    session_id = str(session_id or "").strip()
    if not session_id:
        return _empty_document("")
    path = session_memory_path(session_id)
    document = _read_document(path)
    if document is None:
        return _empty_document(session_id)
    document.setdefault("session_id", session_id)
    document.setdefault("messages", [])
    if not isinstance(document["messages"], list):
        document["messages"] = []
    return document


def _normalize_stored_message(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    msg_type = str(item.get("type") or item.get("role") or "").strip()
    content = str(item.get("content") or "").strip()
    if not content:
        return None
    if msg_type in _HUMAN_TYPES:
        return {"type": MEMORY_HUMAN, "content": content}
    if msg_type in _AI_TYPES:
        return {"type": MEMORY_AI, "content": content}
    return None


def stored_messages_to_llm(messages: list[Any]) -> list[dict[str, str]]:
    """
    Extract only human/ai text for LLM context.

    Strips LangGraph metadata (ids, response_metadata, usage_metadata, etc.).
    """
    out: list[dict[str, str]] = []
    for item in messages:
        normalized = _normalize_stored_message(item)
        if not normalized:
            continue
        role = "user" if normalized["type"] == MEMORY_HUMAN else "assistant"
        out.append({"role": role, "content": normalized["content"]})
    return out


def _completed_pairs_only(messages: list[Any]) -> list[dict[str, str]]:
    """
    Prior turns for LLM context: only human+ai pairs.

    Drops a trailing human without a following ai (in-flight question).
    """
    llm = stored_messages_to_llm(messages)
    if llm and llm[-1].get("role") == "user":
        llm = llm[:-1]
    return llm


def load_session_llm_messages(session_id: str) -> list[dict[str, str]]:
    """Load session memory as clean user/assistant dicts for planner/answer LLMs."""
    document = load_session_memory_file(session_id)
    return _completed_pairs_only(document.get("messages") or [])


def append_user_query(session_id: str, user_query: str) -> bool:
    """
    Record the user's question as soon as it is submitted.

    Called at the start of each turn so the memory file is never empty after Q1.
    """
    user = str(user_query or "").strip()
    if not session_id or not user:
        return False

    path = ensure_session_memory_file(session_id)
    document = load_session_memory_file(session_id)
    messages = document.get("messages")
    if not isinstance(messages, list):
        messages = []

    if (
        messages
        and messages[-1].get("type") == MEMORY_HUMAN
        and str(messages[-1].get("content") or "").strip() == user
    ):
        return True

    messages.append({"type": MEMORY_HUMAN, "content": user})
    document["messages"] = messages
    document["updated_at"] = _utc_now()
    _write_document(path, document)
    return True


def append_assistant_answer(session_id: str, assistant_answer: str) -> bool:
    """Append the final assistant reply when a turn completes."""
    answer = str(assistant_answer or "").strip()
    if not session_id or not answer:
        return False

    path = ensure_session_memory_file(session_id)
    document = load_session_memory_file(session_id)
    messages = document.get("messages")
    if not isinstance(messages, list):
        messages = []

    if (
        messages
        and messages[-1].get("type") == MEMORY_AI
        and str(messages[-1].get("content") or "").strip() == answer
    ):
        return True

    messages.append({"type": MEMORY_AI, "content": answer})
    document["messages"] = messages
    document["updated_at"] = _utc_now()
    _write_document(path, document)
    return True


def append_session_turn(
    session_id: str,
    user_query: str,
    assistant_answer: str,
) -> bool:
    """
    Append one completed turn (human then ai) and rewrite the session file.

    Prefer append_user_query + append_assistant_answer during a live turn.
    """
    user = str(user_query or "").strip()
    answer = str(assistant_answer or "").strip()
    if not session_id or not user or not answer:
        return False

    append_user_query(session_id, user)
    return append_assistant_answer(session_id, answer)


def session_turn_count(session_id: str) -> int:
    """Number of completed human+ai pairs on disk."""
    document = load_session_memory_file(session_id)
    messages = document.get("messages") or []
    pairs = 0
    idx = 0
    while idx + 1 < len(messages):
        if (
            messages[idx].get("type") == MEMORY_HUMAN
            and messages[idx + 1].get("type") == MEMORY_AI
        ):
            pairs += 1
            idx += 2
        else:
            idx += 1
    return pairs


def clear_session_memory_file(session_id: str) -> None:
    """Remove the session memory file (/clear)."""
    session_id = str(session_id or "").strip()
    if not session_id:
        return
    path = session_memory_path(session_id)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return
