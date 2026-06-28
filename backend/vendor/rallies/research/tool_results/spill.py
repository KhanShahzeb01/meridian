"""Spill oversized tool payloads to .rallies/tool-results/ (Wave 2 rank 6)."""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..paths import tool_results_dir

DEFAULT_MAX_INLINE_CHARS = 50_000
PREVIEW_HEAD_CHARS = 12_000
PREVIEW_TAIL_CHARS = 4_000


@dataclass(frozen=True)
class SpillResult:
    text: str
    spilled: bool
    path: Path | None = None
    original_chars: int = 0


def _safe_label(label: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", label.strip())[:60]
    return cleaned or "result"


def spill_path(label: str) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    uid = uuid.uuid4().hex[:8]
    name = f"{stamp}_{_safe_label(label)}_{uid}.txt"
    return tool_results_dir() / name


def build_preview(text: str, max_inline: int) -> str:
    if len(text) <= max_inline:
        return text
    if max_inline <= PREVIEW_HEAD_CHARS + PREVIEW_TAIL_CHARS + 200:
        return text[:max_inline] + "\n...[truncated]..."
    head = text[:PREVIEW_HEAD_CHARS]
    tail = text[-PREVIEW_TAIL_CHARS:]
    omitted = len(text) - PREVIEW_HEAD_CHARS - PREVIEW_TAIL_CHARS
    return (
        f"{head}\n\n"
        f"... [{omitted:,} characters omitted — full result on disk] ...\n\n"
        f"{tail}"
    )


def spill_if_large(
    text: str,
    *,
    label: str = "tool_result",
    max_inline: int = DEFAULT_MAX_INLINE_CHARS,
) -> SpillResult:
    """Return inline text or preview + path when payload exceeds max_inline."""
    if not text:
        return SpillResult(text="", spilled=False, original_chars=0)
    original = len(text)
    if original <= max_inline:
        return SpillResult(text=text, spilled=False, original_chars=original)

    path = spill_path(label)
    path.write_text(text, encoding="utf-8")
    preview = build_preview(text, max_inline)
    notice = (
        f"\n\n---\n"
        f"**Full tool result** ({original:,} chars) saved to:\n`{path}`\n"
        f"Read that file for the complete payload."
    )
    return SpillResult(
        text=preview + notice,
        spilled=True,
        path=path,
        original_chars=original,
    )
