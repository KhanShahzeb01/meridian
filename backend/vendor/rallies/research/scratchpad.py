"""
Append-only JSONL scratchpad for research observability (Dexter-inspired, rallies-local).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import scratchpad_dir


@dataclass
class ToolLimitConfig:
    max_calls_per_tool: int = 3
    similarity_threshold: float = 0.7


@dataclass
class ToolCallCheck:
    allowed: bool = True
    warning: str | None = None


class Scratchpad:
    """Per-query audit log: init, tool_result, thinking."""

    def __init__(self, query: str, limit_config: ToolLimitConfig | None = None) -> None:
        self.limit_config = limit_config or ToolLimitConfig()
        self.filepath = self._create_filepath(query)
        self.tool_call_counts: dict[str, int] = {}
        self.tool_queries: dict[str, list[str]] = {}
        self.pending_warnings: list[str] = []
        self.append({"type": "init", "content": query, "timestamp": _utc_now()})

    @property
    def path(self) -> Path:
        return self.filepath

    def add_thinking(self, content: str) -> None:
        if content and content.strip():
            self.append(
                {"type": "thinking", "content": content.strip(), "timestamp": _utc_now()}
            )

    def add_tool_result(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: str | Any,
    ) -> None:
        self.append(
            {
                "type": "tool_result",
                "timestamp": _utc_now(),
                "toolName": tool_name,
                "args": args,
                "result": _parse_result_safely(result),
            }
        )

    def can_call_tool(
        self,
        tool_name: str,
        query: str | None = None,
        limit_key: str | None = None,
    ) -> ToolCallCheck:
        key = limit_key or tool_name
        current = self.tool_call_counts.get(key, 0)
        max_calls = self.limit_config.max_calls_per_tool

        if current >= max_calls:
            return ToolCallCheck(
                allowed=True,
                warning=(
                    f"Tool '{key}' has been called {current} times "
                    f"(suggested limit: {max_calls})."
                ),
            )

        if query:
            previous = self.tool_queries.get(key, [])
            similar = _find_similar_query(query, previous, self.limit_config.similarity_threshold)
            if similar:
                remaining = max_calls - current
                return ToolCallCheck(
                    allowed=True,
                    warning=(
                        f"Similar repeat call for '{key}' "
                        f"(~{remaining} left before suggested limit)."
                    ),
                )

        if current == max_calls - 1:
            return ToolCallCheck(
                allowed=True,
                warning=(
                    f"Approaching suggested limit for '{key}' ({current + 1}/{max_calls})."
                ),
            )

        return ToolCallCheck(allowed=True)

    def record_tool_call(
        self,
        tool_name: str,
        query: str | None = None,
        limit_key: str | None = None,
    ) -> None:
        key = limit_key or tool_name
        self.tool_call_counts[key] = self.tool_call_counts.get(key, 0) + 1
        if query:
            self.tool_queries.setdefault(key, []).append(query)

    def format_tool_usage_for_prompt(self) -> str | None:
        if not self.tool_call_counts:
            return None
        lines = []
        max_calls = self.limit_config.max_calls_per_tool
        for tool_name, count in sorted(self.tool_call_counts.items()):
            if count >= max_calls:
                status = f"{count} calls (at/over suggested limit of {max_calls})"
            else:
                status = f"{count}/{max_calls} calls"
            lines.append(f"- {tool_name}: {status}")
        body = "\n".join(lines)
        return (
            "## Tool usage this query\n\n"
            f"{body}\n\n"
            "If a source is not returning useful data, try a different tool or rephrase the step."
        )

    def drain_warnings(self) -> list[str]:
        warnings = list(self.pending_warnings)
        self.pending_warnings.clear()
        return warnings

    def append(self, entry: dict[str, Any]) -> None:
        with self.filepath.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def tail_lines(self, n: int = 8) -> list[str]:
        if not self.filepath.exists():
            return []
        lines = self.filepath.read_text(encoding="utf-8").splitlines()
        return lines[-n:]

    def _create_filepath(self, query: str) -> Path:
        digest = hashlib.md5(query.encode("utf-8")).hexdigest()[:12]
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
        return scratchpad_dir() / f"{ts}_{digest}.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_result_safely(result: str | Any) -> Any:
    if not isinstance(result, str):
        return result
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return result


def _tokenize(query: str) -> set[str]:
    words = re.sub(r"[^\w\s]", " ", query.lower()).split()
    return {w for w in words if len(w) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _find_similar_query(
    new_query: str,
    previous: list[str],
    threshold: float,
) -> str | None:
    new_words = _tokenize(new_query)
    for prev in previous:
        if _jaccard(new_words, _tokenize(prev)) >= threshold:
            return prev
    return None
