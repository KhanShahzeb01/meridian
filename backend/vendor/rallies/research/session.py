"""
Research session: scratchpad + rules + tool limits for one user query (Wave 1).
"""

from __future__ import annotations

import re
from typing import Any

from ..ticker_identify import identify_query_tickers
from .prompt_overlay import research_system_prefix
from .scratchpad import Scratchpad, ToolCallCheck
from .tool_registry import build_compact_tool_descriptions


def _limit_key_for_data_tool(tool_name: str, query_key: str | None) -> str:
    """Per-ticker limits for quote/financials (e.g. yfinance_quote:NOW)."""
    if not query_key:
        return tool_name
    parts = [p.strip() for p in query_key.split("|")]
    if parts:
        tail = parts[-1].strip().upper()
        if re.fullmatch(r"[A-Z]{1,6}(?:[.-][A-Z]{1,2})?", tail):
            return f"{tool_name}:{tail}"
    return tool_name


class ResearchSession:
    """Observability context for a single rallies turn (/ask or planner flow)."""

    def __init__(self, query: str) -> None:
        self.query = query
        self.query_tickers: list[str] = identify_query_tickers(query)
        self.prefetched_market_block: str | None = None
        self.scratchpad = Scratchpad(query)
        self.session_follow_up: bool = False
        self.prior_command: str | None = None

    @classmethod
    def begin(cls, query: str) -> ResearchSession:
        return cls(query)

    @property
    def filepath(self) -> str:
        return str(self.scratchpad.path)

    def rules_prefix(self) -> str:
        return research_system_prefix()

    def planner_prompt_addon(self) -> str:
        """Injected into planner prompt: tools + RULES + SOUL — no limit warnings."""
        parts = []
        overlay = self.rules_prefix()
        if overlay:
            parts.append(overlay.strip())
        tools = build_compact_tool_descriptions()
        parts.append(
            "## Available data tools (rallies)\n\n"
            "The executor may fetch live data using these tools during plan steps:\n\n"
            f"{tools}\n"
        )
        if self.session_follow_up and self.prior_command == "/screen":
            tickers = ", ".join(self.query_tickers) if self.query_tickers else "see prior answer"
            parts.append(
                "## Follow-up after /screen\n\n"
                "The prior assistant message contains the screening results table. "
                "When the user mentions **score** or **consensus score**, they mean "
                "the screener's **Score** / average column — not external analyst "
                "Smart Scores or TipRanks consensus.\n\n"
                f"Answer from that screening output first. Tickers from the screen: "
                f"{tickers}.\n\n"
                "Plan only incremental live-data fetches still needed; return [] "
                "when the thread already answers the question."
            )
        elif self.session_follow_up and self.prior_command == "/consensus":
            tickers = ", ".join(self.query_tickers) if self.query_tickers else "see prior answer"
            parts.append(
                "## Follow-up after /consensus\n\n"
                "The prior assistant message contains the expert panel analyses and "
                f"consensus summary for {tickers}. Use that thread context first "
                "(including named experts such as Buffett/value investor). "
                "Plan only what is still missing; return [] when covered."
            )
        elif self.session_follow_up and self.prior_command in ("/ask", "/debate"):
            parts.append(
                f"## Follow-up after {self.prior_command}\n\n"
                "The prior assistant message contains the persona response. "
                "Use that thread context first before fetching new data."
            )
        elif self.session_follow_up and self.prior_command:
            parts.append(
                f"## Follow-up after {self.prior_command}\n\n"
                "Use the prior assistant answer in the thread as the primary source. "
                "Plan only incremental tool calls still required."
            )
        elif self.session_follow_up and self.query_tickers:
            parts.append(
                "## Session follow-up\n\n"
                f"This message continues the current terminal session about "
                f"{', '.join(self.query_tickers)}. "
                "Plan only what is still needed to answer the latest question; "
                "return [] when prior answers in the thread already cover it."
            )
        elif len(self.query_tickers) >= 2:
            parts.append(
                f"## Tickers in this question\n\n"
                f"User asked about: {', '.join(self.query_tickers)}. "
                "Each ticker must appear in your analysis; live data is prefetched when possible."
            )
        elif len(self.query_tickers) == 1:
            parts.append(
                f"## Ticker in this question\n\n"
                f"User asked about: {self.query_tickers[0]}."
            )
        return "\n\n".join(parts) if parts else ""

    def action_prompt_addon(self) -> str:
        """Optional compare reminder only — do not inject tool-limit warnings into action LLM."""
        if len(self.query_tickers) >= 2:
            return (
                f"Remember: the user's question covers {', '.join(self.query_tickers)}. "
                "Use the prefetched live data block and analyze every ticker."
            )
        return ""

    def check_tool(
        self,
        tool_name: str,
        query: str | None = None,
        limit_key: str | None = None,
    ) -> ToolCallCheck:
        key = limit_key or tool_name
        check = self.scratchpad.can_call_tool(tool_name, query, limit_key=key)
        if check.warning:
            self.scratchpad.pending_warnings.append(check.warning)
        return check

    def record_data_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: str,
        query_key: str | None = None,
    ) -> ToolCallCheck:
        q = query_key or str(args)
        limit_key = _limit_key_for_data_tool(tool_name, query_key)
        check = self.check_tool(tool_name, q, limit_key=limit_key)
        self.scratchpad.record_tool_call(tool_name, q, limit_key=limit_key)
        preview = result if len(result) <= 8000 else result[:8000] + "\n...[truncated for scratchpad]..."
        self.scratchpad.add_tool_result(tool_name, args, preview)
        return check

    def record_llm_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: str,
    ) -> None:
        self.scratchpad.record_tool_call(tool_name)
        preview = result if len(result) <= 12000 else result[:12000] + "\n...[truncated]..."
        self.scratchpad.add_tool_result(tool_name, args, preview)

    def notify_loop_warning(self, message: str) -> None:
        self.scratchpad.pending_warnings.append(message)
