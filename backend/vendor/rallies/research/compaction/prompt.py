"""Compaction prompts — port of Dexter compact.ts (text-only summarization)."""

from __future__ import annotations

_NO_TOOLS_PREAMBLE = """CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.

- Do NOT use any tool calls. You already have all the context you need below.
- Your entire response must be plain text: an <analysis> block followed by a <summary> block.

"""

_ANALYSIS_INSTRUCTION = """Before providing your final summary, wrap your analysis in <analysis> tags.

1. Chronologically review each tool call and its results.
2. Preserve all key numbers, dates, and ticker-specific findings.
"""

_BASE_COMPACT_PROMPT = f"""Your task is to create a detailed summary of the research session below.

{_ANALYSIS_INSTRUCTION}

Your summary must include:
1. Original Query and Intent
2. Key Concepts (tickers, metrics)
3. Data Retrieved (per tool: args + key results)
4. Errors and Retries
5. Analysis Progress
6. Numerical Data (ALL prices, margins, ratios — do not omit)
7. Pending Data Needs
8. Current Work State
9. Recommended Next Steps

Structure your output as <analysis>...</analysis> then <summary>...</summary>.
"""

_NO_TOOLS_TRAILER = (
    "\n\nREMINDER: Plain text only — <analysis> then <summary>. No tool calls."
)


def build_compaction_prompt(query: str, tool_results: str) -> str:
    return (
        f"{_NO_TOOLS_PREAMBLE}{_BASE_COMPACT_PROMPT}\n\n"
        f"Original query: {query}\n\n"
        f"Data retrieved from tool calls:\n{tool_results}{_NO_TOOLS_TRAILER}"
    )


def format_compact_summary(raw_summary: str) -> str:
    """Strip <analysis> and normalize <summary> for injection."""
    formatted = raw_summary or ""
    formatted = _strip_tag_block(formatted, "analysis")
    match = _extract_tag_content(formatted, "summary")
    if match is not None:
        formatted = formatted.replace(
            f"<summary>{match}</summary>",
            f"Summary:\n{match.strip()}",
            1,
        )
        formatted = _strip_tag_block(formatted, "summary")
    while "\n\n\n" in formatted:
        formatted = formatted.replace("\n\n\n", "\n\n")
    return formatted.strip()


def build_compact_summary_message(summary: str) -> str:
    formatted = format_compact_summary(summary)
    return (
        "This session continues from a previous research pass that ran out of context. "
        "The summary below covers data retrieved and analysis so far.\n\n"
        f"{formatted}\n\n"
        "Continue toward answering the query without asking the user new questions. "
        "Resume directly — do not recap the summary."
    )


def _strip_tag_block(text: str, tag: str) -> str:
    import re

    return re.sub(rf"<{tag}>[\s\S]*?</{tag}>", "", text, flags=re.IGNORECASE)


def _extract_tag_content(text: str, tag: str) -> str | None:
    import re

    match = re.search(rf"<{tag}>([\s\S]*?)</{tag}>", text, flags=re.IGNORECASE)
    return match.group(1) if match else None
