"""Export and resume REPL conversation state as markdown files."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPORT_FORMAT = "rallies-conversation-v1"
_EXPORT_JSON_RE = re.compile(
    r"```json\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)


def get_exports_dir() -> Path:
    """Directory for saved conversation markdown files."""
    from .helpers import get_config_dir

    exports_dir = get_config_dir() / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    return exports_dir


def default_export_filename(now: datetime | None = None) -> str:
    """Timestamped filename: chat_YYYY-MM-DD_HHMMSS.md"""
    ts = now or datetime.now()
    return f"chat_{ts.strftime('%Y-%m-%d_%H%M%S')}.md"


def normalize_messages(conversation: list) -> list[dict[str, Any]]:
    """Serializable message list for export/resume."""
    out: list[dict[str, Any]] = []
    for item in conversation:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant") or content is None:
            continue
        text = str(content).strip()
        if not text:
            continue
        msg: dict[str, Any] = {"role": role, "content": str(content)}
        msg_type = item.get("type")
        if msg_type:
            msg["type"] = msg_type
        out.append(msg)
    return out


def conversation_to_markdown(
    conversation: list,
    *,
    source_path: str | None = None,
    exported_at: datetime | None = None,
) -> str:
    """Human-readable markdown with embedded JSON for reliable reload."""
    exported_at = exported_at or datetime.now(timezone.utc)
    messages = normalize_messages(conversation)
    payload = {
        "format": EXPORT_FORMAT,
        "exported_at": exported_at.isoformat(),
        "message_count": len(messages),
        "messages": messages,
    }
    if source_path:
        payload["source_path"] = source_path

    lines = [
        "# Rallies conversation export",
        "",
        f"- **Exported:** {exported_at.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- **Messages:** {len(messages)}",
        f"- **Format:** `{EXPORT_FORMAT}`",
        "",
        "Read the transcript below, or reload in the CLI with:",
        "",
        "```text",
        f"/resume {source_path or '<path-to-this-file>'}",
        "```",
        "",
        "---",
        "",
    ]

    for i, msg in enumerate(messages, start=1):
        role = msg["role"].title()
        lines.append(f"## {i}. {role}")
        lines.append("")
        lines.append(str(msg["content"]))
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Machine-readable snapshot")
    lines.append("")
    lines.append(
        "The block below is used by `/resume`. Do not edit unless you know the format."
    )
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(payload, indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def parse_export_file(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load messages and metadata from an export markdown file."""
    text = path.read_text(encoding="utf-8")
    match = _EXPORT_JSON_RE.search(text)
    if not match:
        raise ValueError(
            "No rallies conversation JSON block found. "
            "Use a file created with /export."
        )
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in export file: {e}") from e

    if payload.get("format") != EXPORT_FORMAT:
        raise ValueError(
            f"Unsupported export format: {payload.get('format')!r}. "
            f"Expected {EXPORT_FORMAT!r}."
        )

    raw_messages = payload.get("messages")
    if not isinstance(raw_messages, list):
        raise ValueError("Export file is missing a messages array.")

    messages: list[dict[str, Any]] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant"):
            continue
        if content is None or not str(content).strip():
            continue
        msg: dict[str, Any] = {"role": role, "content": str(content)}
        if item.get("type"):
            msg["type"] = item["type"]
        messages.append(msg)

    if not messages:
        raise ValueError("Export file contains no restorable messages.")

    meta = {
        "exported_at": payload.get("exported_at"),
        "message_count": payload.get("message_count", len(messages)),
        "source_path": str(path.resolve()),
    }
    return messages, meta


def export_conversation(
    conversation: list,
    *,
    dest: Path | None = None,
) -> Path:
    """Write conversation to markdown; return path written."""
    messages = normalize_messages(conversation)
    if not messages:
        raise ValueError("Nothing to export — conversation is empty.")

    if dest is None:
        dest = get_exports_dir() / default_export_filename()
    else:
        dest = Path(dest).expanduser().resolve()
        if dest.suffix.lower() != ".md":
            dest = dest.with_suffix(".md")
        dest.parent.mkdir(parents=True, exist_ok=True)

    body = conversation_to_markdown(
        conversation,
        source_path=str(dest),
    )
    dest.write_text(body, encoding="utf-8")
    return dest


def resume_conversation(conversation: list, path: Path) -> dict[str, Any]:
    """Replace conversation in place from an export file; return metadata."""
    messages, meta = parse_export_file(path)
    conversation[:] = messages
    return meta
