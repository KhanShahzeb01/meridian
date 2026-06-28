from __future__ import annotations

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING

from .prompts import agent_prompt, answer_prompt, summary_prompt, compact_prompt
from ..llm import LLM, LLMError
from ..llm_user_message import format_llm_error_rich
from ..ticker_identify import identify_query_tickers

if TYPE_CHECKING:
    from ..research.session import ResearchSession


class Agent:
    def __init__(self, api_key=None, llm=None, data_registry=None, status_callback=None):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.api_key = api_key
        self.llm = llm or LLM(api_key=api_key)
        self.data_registry = data_registry
        self.status_callback = status_callback
        self.research_session: ResearchSession | None = None
        self.user_query: str | None = None
        self.last_usage = 0
        self.last_limit = 0

    def set_research_session(self, session: ResearchSession | None) -> None:
        self.research_session = session

    def set_user_query(self, query: str | None) -> None:
        self.user_query = query

    def _emit_research_warning(self, message: str) -> None:
        # Log only — do not spam planning UI or inject into LLM prompts.
        if self.research_session:
            self.research_session.notify_loop_warning(message)

    def _resolve_tickers(self, text: str) -> list[str]:
        merged = identify_query_tickers(text) + identify_query_tickers(
            self.user_query or ""
        )
        session = self.research_session
        if session and session.query_tickers:
            merged = session.query_tickers + merged
        return list(dict.fromkeys(merged))[:5]

    def build_compare_prefetch(
        self, tickers: list[str], *, max_tickers: int | None = 5
    ) -> str:
        """One-shot live data for all tickers in a compare question."""
        if not self.data_registry or not tickers:
            return ""
        lines = [
            "## Prefetched live market data (all tickers in user question)",
            "Use these exact figures. Do not ask the user to fetch more data.",
        ]
        yfs = self.data_registry.get_source("yfinance")
        if not yfs:
            return ""
        use = tickers if max_tickers is None else tickers[:max_tickers]
        from ..quotes import format_yfinance_quote_line

        for ticker in use:
            data = yfs.get_quote(ticker)
            if data and "error" not in data:
                quote_line = format_yfinance_quote_line(data)
                lines.append(quote_line)
                self._maybe_record_tool(
                    "yfinance_quote",
                    f"prefetch | {ticker}",
                    quote_line,
                )
            fin = yfs.get_financials(ticker, years=3)
            if fin and "error" not in fin:
                rev_row = net_row = None
                for r in fin.get("rows", []):
                    if r["label"] == "Total Revenue":
                        rev_row = r
                    if r["label"] == "Net Income":
                        net_row = r
                fin_lines = [f"--- {ticker} Financials ---"]
                if rev_row:
                    vals = []
                    for i, v in enumerate(rev_row["values"]):
                        period = fin["periods"][i] if i < len(fin["periods"]) else ""
                        if v:
                            vals.append(f"{period}: ${v/1e9:.2f}B")
                    fin_lines.append("Revenue: " + " | ".join(vals))
                if net_row:
                    vals = []
                    for i, v in enumerate(net_row["values"]):
                        period = fin["periods"][i] if i < len(fin["periods"]) else ""
                        if v:
                            vals.append(f"{period}: ${v/1e9:.2f}B")
                    fin_lines.append("Net Income: " + " | ".join(vals))
                block = "\n".join(fin_lines)
                lines.append(block)
                self._maybe_record_tool(
                    "yfinance_financials",
                    f"prefetch | {ticker}",
                    block,
                )
        return "\n".join(lines)
        
    def parse_messages(self, messages: list) -> list:
         parsed_messages = []
         for message in messages:
             if isinstance(message, dict) and "role" in message and "content" in message:
                 parsed_messages.append({
                     "role": message["role"],
                     "content": message["content"]
                 })
         return parsed_messages

    def set_api_key(self, api_key):
        self.api_key = api_key
        self.llm.api_key = api_key

    def _resilient_action_prompt(self, messages):
        """Run action prompt with a narrow retry policy for empty provider payloads.

        This only retries when the provider returns an empty assistant response
        (`reason_code == "empty_response"`). Non-empty-response errors are re-raised
        immediately to avoid masking genuine issues.
        """
        fallback_candidates = []
        models_cfg = self.llm.provider_config.get("models", {})
        for model_name in (
            models_cfg.get("heavy"),
            models_cfg.get("cheap"),
            *self.llm.provider_config.get("free_fallback_models", []),
        ):
            if model_name and model_name not in fallback_candidates:
                fallback_candidates.append(model_name)

        attempts = [
            {"force_model": None, "no_cache": False},  # normal path
            {"force_model": None, "no_cache": True},   # fresh retry
        ]
        attempts.extend(
            {"force_model": model_name, "no_cache": True}
            for model_name in fallback_candidates
        )

        last_empty_error = None
        for idx, attempt in enumerate(attempts, start=1):
            try:
                return self.llm.prompt(
                    messages,
                    task_type="action",
                    force_model=attempt["force_model"],
                    no_cache=attempt["no_cache"],
                )
            except LLMError as e:
                if e.reason_code == "empty_response":
                    last_empty_error = e
                    if callable(self.status_callback) and idx < len(attempts):
                        next_attempt = attempts[idx]
                        model = next_attempt.get("force_model")
                        if model:
                            self.status_callback(
                                f"Provider returned empty response. Retrying with model `{model}`..."
                            )
                        else:
                            self.status_callback(
                                "Provider returned empty response. Retrying with a fresh request..."
                            )
                    continue
                raise

        if last_empty_error:
            raise last_empty_error
        raise LLMError("No usable model response", reason_code="empty_response")

    def run(self, messages: str, max_steps=None) -> str:
        message = []
        planner_prompt = agent_prompt
        if max_steps:
            planner_prompt += (
                f"\nFor this planning round, return a complete bounded plan with at most "
                f"{int(max_steps)} steps. Prefer a complete plan in one pass. "
                "Only return [] when the gathered context is enough for a final answer."
            )
        session = self.research_session
        if session:
            addon = session.planner_prompt_addon()
            if addon:
                planner_prompt += f"\n\n{addon}"
            session.scratchpad.add_thinking("Planner round starting")
        message.append({"role": "developer", "content": planner_prompt})
        message.extend(self.parse_messages(messages))
        response = self.llm.prompt(message, requires_json=True, task_type="planner")
        if session:
            session.record_llm_tool(
                "planner_llm",
                {"max_steps": max_steps},
                str(response)[:12000],
            )
        return response
    
    def _maybe_record_tool(self, tool_name: str, query_key: str, payload: str) -> None:
        session = self.research_session
        if not session or not payload:
            return
        check = session.record_data_tool(
            tool_name,
            {"query": query_key},
            payload,
            query_key=query_key,
        )
        if check.warning:
            self._emit_research_warning(check.warning)

    def _get_real_data(self, title, description, question):
        if self.data_registry is None:
            return None
        text = f"{title} {description} {question}"
        low_text = text.lower()
        query_key = f"{title} | {description}"

        lines = []

        # --- Non-ticker routes (run regardless of ticker presence) ---

        # Route to FRED for macro/economic queries
        is_macro = any(w in low_text for w in [
            "economy", "economic", "macro", "gdp", "interest rate", "inflation",
            "cpi", "unemployment", "fed", "federal reserve", "treasury yield",
        ])
        if is_macro:
            source = self.data_registry.get_source("fred")
            if source and source.available:
                result = source.get_macro_summary()
                if result and "error" not in result:
                    data = result.data if hasattr(result, "data") else result
                    macro_lines = ["\n--- Economic Indicators ---"]
                    for sid in ["FEDFUNDS", "CPIAUCSL", "UNRATE", "DGS10", "GDPC1"]:
                        entry = data.get(sid)
                        if entry:
                            val = entry.get("value", "")
                            macro_lines.append(
                                f"{entry.get('label', sid)}: {val}"
                                f"{'%' if sid not in ('GDPC1','SP500') else ''} "
                                f"(as of {entry.get('date', '')})"
                            )
                    block = "\n".join(macro_lines)
                    lines.extend(macro_lines)
                    self._maybe_record_tool("fred_macro", query_key, block)

        # Route to Hedge Fund Monitor for HF/positioning queries
        is_hf = any(w in low_text for w in [
            "hedge fund", "hedgefund", "institutional", "positioning",
            "leverage", "fund flow",
        ])
        if is_hf:
            source = self.data_registry.get_source("hedgefund")
            if source:
                result = source.get_snapshot()
                if result:
                    data = result.data if hasattr(result, "data") else result
                    hf_lines = ["\n--- Hedge Fund Data ---"]
                    for entry in data.values():
                        val = entry.get("value", "")
                        hf_lines.append(f"{entry.get('label', '')}: {val}")
                    block = "\n".join(hf_lines)
                    lines.extend(hf_lines)
                    self._maybe_record_tool("hedgefund_snapshot", query_key, block)

        # Route to CBOE for VIX/volatility queries
        is_vix = any(w in low_text for w in [
            "vix", "volatility", "fear", "fear index",
        ])
        if is_vix:
            source = self.data_registry.get_source("cboe")
            if source:
                result = source.get_vix()
                if result:
                    v = result.data
                    vix_line = (
                        f"\n--- VIX: {v.get('vix', '')} "
                        f"(change: {v.get('change_pct', '')}) ---"
                    )
                    lines.append(vix_line)
                    self._maybe_record_tool("cboe_vix", query_key, vix_line)

        # --- Ticker-dependent routes ---
        tickers = self._resolve_tickers(text)
        if not tickers:
            return "\n".join(lines) if lines else None

        yfs = self.data_registry.get_source("yfinance")
        tickers_for_sequential_quotes = list(tickers[:3])

        # Single ticker: parallel quote + SEC (Wave 2) — avoids duplicate sequential quote.
        if len(tickers) == 1:
            from ..research.batch.ticker_bundle import parallel_quote_sec_bundle

            bundle = parallel_quote_sec_bundle(self.data_registry, tickers[0])
            for rec in bundle:
                lines.append(rec.line)
                self._maybe_record_tool(
                    rec.tool_name,
                    f"{query_key} | {rec.query_suffix}",
                    rec.line,
                )
            tickers_for_sequential_quotes = []

        if yfs and tickers_for_sequential_quotes:
            for ticker in tickers_for_sequential_quotes:
                data = yfs.get_quote(ticker)
                if data and "error" not in data:
                    from ..research.batch.quote_format import format_quote_line

                    quote_line = format_quote_line(ticker, data)
                    if quote_line:
                        lines.append(quote_line)
                        self._maybe_record_tool(
                            "yfinance_quote",
                            f"{query_key} | {ticker}",
                            quote_line,
                        )

        # Route to yfinance financials when step mentions financial statements
        is_financials = any(w in low_text for w in [
            "financial", "income", "revenue", "earnings", "profit", "margin",
            "balance sheet", "cash flow", "statement", "quarterly result",
        ])
        if is_financials and yfs:
            for ticker in tickers[:2]:
                data = yfs.get_financials(ticker, years=3)
                if data and "error" not in data:
                    rev_row = None
                    net_row = None
                    for r in data.get("rows", []):
                        if r["label"] == "Total Revenue":
                            rev_row = r
                        if r["label"] == "Net Income":
                            net_row = r
                    fin_lines = [f"\n--- {ticker} Financials ---"]
                    if rev_row:
                        vals = []
                        for i, v in enumerate(rev_row["values"]):
                            period = data["periods"][i] if i < len(data["periods"]) else ""
                            if v:
                                vals.append(f"{period}: ${v/1e9:.2f}B")
                        fin_lines.append("Revenue: " + " | ".join(vals))
                    if net_row:
                        vals = []
                        for i, v in enumerate(net_row["values"]):
                            period = data["periods"][i] if i < len(data["periods"]) else ""
                            if v:
                                vals.append(f"{period}: ${v/1e9:.2f}B")
                        fin_lines.append("Net Income: " + " | ".join(vals))
                    block = "\n".join(fin_lines)
                    lines.extend(fin_lines)
                    self._maybe_record_tool(
                        "yfinance_financials",
                        f"{query_key} | {ticker}",
                        block,
                    )

        # Route to edgartools insider trades when step mentions insider activity
        is_insider = any(w in low_text for w in [
            "insider", "form 4", "insider trade", "insider sell", "insider buy",
            "executive trade", "director trade",
        ])
        if is_insider:
            edgar = self.data_registry.get_source("edgartools")
            if edgar:
                for ticker in tickers[:2]:
                    trades = edgar.get_insider_trades(ticker, count=5)
                    if trades and len(trades) > 0 and "error" not in trades[0]:
                        insider_lines = [f"\n--- {ticker} Insider Activity ---"]
                        for txn in trades:
                            if "info" in txn:
                                insider_lines.append(txn["info"])
                            else:
                                ttype = txn.get("type", "")
                                shares = txn.get("shares", "")
                                price = txn.get("price", "")
                                owner = txn.get("owner", "")
                                date = txn.get("date", "")
                                if isinstance(shares, (int, float)):
                                    shares = f"{shares:,.0f}"
                                if isinstance(price, (int, float)):
                                    price = f"${price:.2f}"
                                insider_lines.append(
                                    f"{date} | {owner} | {ttype} | {shares} shares @ {price}"
                                )
                        block = "\n".join(insider_lines)
                        lines.extend(insider_lines)
                        self._maybe_record_tool(
                            "edgartools_insider",
                            f"{query_key} | {ticker}",
                            block,
                        )

        # Route to Finnhub for news (concise: max 3 headlines)
        is_news = any(w in low_text for w in [
            "news", "headline", "recent development",
        ])
        if is_news:
            finnhub = self.data_registry.get_source("finnhub")
            if finnhub and finnhub.available:
                for ticker in tickers[:2]:
                    result = finnhub.get_company_news(ticker, max_items=3)
                    if result:
                        news_lines = [f"\n--- {ticker} News ---"]
                        for art in result.data.get("headlines", [])[:3]:
                            hl = art.get("headline", "")[:100]
                            src = art.get("source", "")
                            news_lines.append(f"  [{src}] {hl}")
                        block = "\n".join(news_lines)
                        lines.extend(news_lines)
                        self._maybe_record_tool(
                            "finnhub_news",
                            f"{query_key} | {ticker}",
                            block,
                        )

        return "\n".join(lines) if lines else None

    def action(self, question, title, description, conversation=None):
        try:
            today = datetime.now().date().isoformat()
            step_prompt = (
                f"Current date: {today}\n"
                f"User question: {question}\n"
                f"Current task title: {title}\n"
                f"Current task description: {description}\n\n"
                "Return actionable findings for this specific task. "
                "For market prices, news, performance, technicals, financials, "
                "or analyst data, verify the latest available information and "
                "include the date or timestamp. Do not use stale historical data "
                "as current data."
            )
            data_blocks = []
            session = self.research_session
            if session and session.prefetched_market_block:
                data_blocks.append(session.prefetched_market_block)
            real_data = self._get_real_data(title, description, question)
            if real_data:
                data_blocks.append(real_data)
            if data_blocks:
                combined = "\n\n".join(data_blocks)
                from ..research.tool_results import spill_if_large

                spilled = spill_if_large(
                    combined,
                    label=f"action_{title[:48]}",
                )
                if spilled.spilled and session:
                    session.scratchpad.add_thinking(
                        f"Spilled large data block ({spilled.original_chars} chars) "
                        f"to {spilled.path}"
                    )
                combined = spilled.text
                step_prompt = (
                    f"## CRITICAL — Live market data (you MUST use these exact numbers)\n"
                    f"The following is live, verified data retrieved right now. You MUST use these exact values.\n"
                    f"Do NOT use any price, multiple, or metric from your training data. Only use what is below.\n"
                    f"Do NOT tell the user to fetch data — analyze every ticker listed.\n"
                    f"{combined}\n\n---\n\n{step_prompt}"
                )
            # For synthesis steps, include current gathered context
            if conversation:
                summaries = []
                for msg in conversation[-4:]:
                    if isinstance(msg.get("content"), str) and len(msg["content"]) > 20:
                        summaries.append(msg["content"][:500])
                if summaries:
                    step_prompt += (
                        "\n\nContext already gathered:\n" + "\n---\n".join(summaries)
                    )
            session = self.research_session
            if session:
                addon = session.action_prompt_addon()
                if addon:
                    step_prompt += f"\n\n{addon}"
                session.scratchpad.add_thinking(f"Action step: {title}")
            messages = [
                {
                    "role": "system",
                    "content": self.llm.provider_config.get(
                        "system_prompt",
                        "You are a market research retrieval assistant.",
                    ),
                },
                {"role": "user", "content": step_prompt},
            ]
            response = self._resilient_action_prompt(messages)
            self.last_usage = self.llm.last_usage
            self.last_limit = self.llm.last_limit
            if session:
                session.record_llm_tool(
                    "action_llm",
                    {"title": title, "description": description},
                    str(response or "")[:12000],
                )
            return response or "No results returned"

        except LLMError as e:
            model = getattr(self.llm, "last_model", None)
            raise Exception(format_llm_error_rich(e, model=model))
        except ValueError as e:
            raise Exception(f"[red]⚠ Configuration Error:[/red] {str(e)}")
        except Exception as e:
            if "[red]" in str(e):
                raise
            raise Exception(f"[red]⚠ Error:[/red] {str(e)}")
    
    def summarize(self, messages):
        message = []
        message.append({"role": "developer", "content": summary_prompt})
        message.extend(self.parse_messages(messages))
        summary = self.llm.prompt(message, task_type="summary")
        return summary
    
    def answer(self, question, messages):
        message = []
        answer_prompt_formatted = answer_prompt.replace("--question--", question)
        message.append({"role": "developer", "content": answer_prompt_formatted})
        message.extend(self.parse_messages(messages))
        for chunk in self.llm.prompt_stream(message, task_type="answer"):
            yield chunk

    def compact(self, messages):
        message = []
        message.append({"role": "developer", "content": compact_prompt})
        message.extend(self.parse_messages(messages))
        try:
            summary = self.llm.prompt(message, task_type="compact")
            if not summary or not str(summary).strip():
                return messages
            messages.clear()
            messages.append({"role": "user", "content": summary})
        except Exception:
            pass
        return messages

        messages.clear()
        messages.append({"role": "user", "content": summary})
        return messages
