from . import console
from .agent.agent import Agent
from .agent.prompts import agent_prompt
from rich.spinner import Spinner
from rich.live import Live
from rich.panel import Panel
from rich.markdown import Markdown
from .helpers import (
    get_timeout_message,
    TokenCounter,
    handle_command,
    get_api_key,
    load_or_create_history_session,
    append_history_event,
    log_turn_aborted,
)
from .llm import LLMError
from .llm_user_message import format_llm_error_rich
from .llm import clean_model_text
from .storage import Storage
from .sources.registry import DataRegistry
from .sources.yfinance_source import YFinanceSource
from .sources.edgartools_source import EdgarToolsSource
from .sources.fred_source import FREDSource
from .sources.hedgefund_source import HedgeFundSource
from .sources.finnhub_source import FinnhubSource
from .sources.reddit_source import RedditSource
from .sources.cboe_source import CBOESource
from .sources.sec_source import SECSource
from .research import ResearchSession, ensure_default_rules_template, ensure_default_soul_template
from .thread_memory import (
    new_turn_workspace,
    record_assistant_turn,
    record_user_query,
    resolve_follow_up,
    should_inject_compare_prefetch,
)
from .token_budgets import TokenBudgetPolicy
import requests
import re

class Manager:
    def __init__(self):
        self.tier = "free"
        api_key = get_api_key()
        self.storage = Storage()
        self.data_registry = DataRegistry()
        self.data_registry.register(YFinanceSource())
        self.data_registry.register(EdgarToolsSource())
        self.data_registry.register(FREDSource())
        self.data_registry.register(HedgeFundSource())
        self.data_registry.register(FinnhubSource())
        self.data_registry.register(RedditSource())
        self.data_registry.register(CBOESource())
        self.data_registry.register(SECSource())
        self.agent = Agent(
            api_key=api_key,
            data_registry=self.data_registry,
            status_callback=self._notify_status,
        )
        self.system_prompt = agent_prompt
        self.token_counter = TokenCounter()
        planning_config = self.agent.llm.provider_config.get("planning", {})
        self.max_planner_rounds = max(1, int(planning_config.get("max_rounds", 1)))
        self.max_steps_per_round = max(1, int(planning_config.get("max_steps_per_round", 5)))
        fast_path_config = self.agent.llm.provider_config.get("fast_path", {})
        self.simple_ticker_fast_path = bool(
            fast_path_config.get("simple_ticker_enabled", True)
        )
        self.history_session = load_or_create_history_session()
        self.research_session: ResearchSession | None = None
        self.token_budget = TokenBudgetPolicy.from_provider_config(
            self.agent.llm.provider_config
        )
        self.thread_max_tokens = self.token_budget.max_thread_tokens
        self._resolved_turn = None
        ensure_default_rules_template()
        ensure_default_soul_template()
        append_history_event(
            self.history_session,
            "session_started",
            {"tier": self.tier},
        )

    def _session_id(self) -> str:
        return str((self.history_session or {}).get("id") or "")

    def begin_research_session(
        self, query: str, conversation: list | None = None
    ) -> ResearchSession:
        """Start observability scratchpad for one user turn (additive)."""
        resolved = resolve_follow_up(
            conversation or [], query, session_id=self._session_id()
        )
        self._resolved_turn = resolved
        record_user_query(resolved.raw_prompt, session_id=self._session_id())

        session = ResearchSession.begin(resolved.raw_prompt)
        session.query_tickers = list(resolved.active_tickers)[:5]
        session.session_follow_up = resolved.is_follow_up
        session.prior_command = resolved.prior_command
        self.research_session = session
        self.agent.set_research_session(session)
        self.agent.set_user_query(resolved.raw_prompt)
        tickers = session.query_tickers
        if len(tickers) >= 2:
            self._notify_status(
                f"Prefetching live data for {', '.join(tickers)}..."
            )
            session.prefetched_market_block = self.agent.build_compare_prefetch(tickers)
        return session

    def end_research_session(self, notify: bool = True) -> None:
        session = self.research_session
        self.research_session = None
        self.agent.set_research_session(None)
        self.agent.set_user_query(None)
        if notify and session:
            console.print(
                f"[dim]Research log: {session.filepath}[/dim]"
            )
            self._print_session_memory_status()
            # Tool-limit notices stay in the scratchpad file only — not user-facing.
            session.scratchpad.drain_warnings()

    def _print_session_memory_status(self) -> None:
        from .graph.flags import turn_pair_memory_enabled
        from .memory.file_store import session_memory_path, session_turn_count

        if not turn_pair_memory_enabled():
            return
        session_id = self._session_id()
        if not session_id:
            return
        path = session_memory_path(session_id)
        turns = session_turn_count(session_id)
        console.print(
            f"[dim]Session memory: {path} ({turns} completed turn"
            f"{'s' if turns != 1 else ''})[/dim]"
        )

    def _run_step_action(self, prompt, item):
        return self.agent.action(prompt, item["title"], item["description"])

    def _notify_status(self, message):
        console.print(f"[bright_black]{message}[/bright_black]")

    def _is_simple_ticker_prompt(self, prompt):
        text = prompt.strip()
        if not self.simple_ticker_fast_path or not text:
            return False
        if any(char.isspace() for char in text):
            return False
        if text.startswith("$"):
            text = text[1:]
        common_words = {
            "buy", "crypto", "fed", "help", "hold", "list",
            "macro", "market", "news", "rate", "rates", "risk",
            "scan", "sell", "stock", "stocks", "today",
            "go", "he", "if", "in", "is", "it", "me", "my",
            "no", "of", "on", "or", "to", "up", "us", "we",
        }
        if text.lower() in common_words:
            return False
        return bool(re.fullmatch(r"[A-Za-z]{2,6}(?:[.-][A-Za-z]{1,2})?", text))

    def process_prompt(self, prompt: str, conversation: list) -> str:
        # Handle commands using helpers
        if handle_command(prompt, conversation, self.agent, console, manager=self):
            return ""
        append_history_event(
            self.history_session,
            "user_prompt",
            {"prompt": prompt},
        )

        try:
            return self._process_prompt_body(prompt, conversation)
        except KeyboardInterrupt:
            log_turn_aborted(
                self.history_session,
                "user_interrupt",
                "Keyboard interrupt during this turn (Ctrl+C).",
            )
            raise
        except LLMError as e:
            log_turn_aborted(
                self.history_session,
                e.reason_code,
                str(e),
                http_status=e.http_status,
            )
            model = getattr(self.agent.llm, "last_model", None)
            console.print(
                format_llm_error_rich(e, model=model, include_technical=False)
            )
            console.print()
            return ""
        except requests.exceptions.Timeout as e:
            log_turn_aborted(self.history_session, "timeout", str(e))
            console.print(f"[red]Request timed out:[/red] {e}")
            console.print()
            return ""
        except requests.exceptions.RequestException as e:
            log_turn_aborted(self.history_session, "network", str(e))
            console.print(f"[red]Network error:[/red] {e}")
            console.print()
            return ""
        except Exception as e:
            log_turn_aborted(
                self.history_session,
                "unknown_error",
                str(e),
                exception_type=type(e).__name__,
            )
            console.print(f"[red]Unexpected error:[/red] {e}")
            console.print()
            return ""

    def _process_prompt_body(self, prompt: str, conversation: list) -> str:
        self.begin_research_session(prompt, conversation)
        resolved = self._resolved_turn
        workspace = new_turn_workspace(
            conversation,
            raw_prompt=prompt,
            effective_prompt=resolved.effective_prompt if resolved else prompt,
            max_tokens=self.thread_max_tokens,
            session_id=self._session_id(),
        )
        if resolved and resolved.is_follow_up:
            console.print(
                f"[dim]Session follow-up"
                f" — continuing {', '.join(resolved.active_tickers[:3])}"
                f"{'…' if len(resolved.active_tickers) > 3 else ''}[/dim]"
            )
        answer = ""
        simple_ticker = self._is_simple_ticker_prompt(prompt)
        try:
            if simple_ticker:
                answer = self._process_simple_ticker_prompt(prompt, workspace, conversation)
            else:
                answer = self._process_planned_prompt(prompt, workspace, conversation)
            return answer
        finally:
            from .graph.hooks import maybe_save_turn_checkpoint

            maybe_save_turn_checkpoint(
                self,
                prompt,
                conversation,
                answer=answer,
                simple_ticker=simple_ticker,
            )
            self.end_research_session()
            self._resolved_turn = None

    def _process_planned_prompt(
        self, prompt: str, workspace: list, thread: list
    ) -> str:
        from .graph.planner.dispatch import run_planned_prompt

        return run_planned_prompt(self, prompt, workspace, thread)

    def _process_simple_ticker_prompt(self, prompt, workspace, thread):
        console.print()
        ticker = prompt.strip().lstrip("$").upper()
        item = {
            "title": f"Get latest verified market snapshot for {ticker}",
            "description": "Let me verify latest price news technicals",
        }
        append_history_event(
            self.history_session,
            "plan_generated",
            {"plan": [item], "fast_path": "simple_ticker"},
        )

        planning_content = [
            f"[bright_green]●[/bright_green] [white]{item['description']}[/white]",
            "[yellow]  Retrieving data...[/yellow]",
        ]
        with Live(
            Panel("\n".join(planning_content), title="Planning", style="magenta"),
            console=console,
            refresh_per_second=4,
        ) as planning_live:
            append_history_event(
                self.history_session,
                "plan_step_started",
                {
                    "title": item["title"],
                    "description": item["description"],
                    "fast_path": "simple_ticker",
                },
            )
            result = self.agent.action(prompt, item["title"], item["description"])
            if "[red]⚠" in result:
                append_history_event(
                    self.history_session,
                    "plan_step_error",
                    {"title": item.get("title"), "error": result},
                )
                log_turn_aborted(
                    self.history_session,
                    "plan_step_failed",
                    result[:2000],
                    step_title=item.get("title"),
                )
                planning_live.stop()
                console.print(result)
                console.print()
                return ""

            workspace.append(
                {
                    "role": "user",
                    "content": f"{item['title']} - {item['description']}",
                }
            )
            workspace.append({"role": "user", "content": str(result), "type": "data"})
            append_history_event(
                self.history_session,
                "plan_step_completed",
                {
                    "title": item["title"],
                    "description": item["description"],
                    "result": str(result),
                    "summary": "Fast path gathered key ticker context in one step.",
                    "fast_path": "simple_ticker",
                },
            )
            planning_content[-1] = (
                "[white]└─[/white] [bright_black]Fast path gathered key ticker context.[/bright_black]"
            )
            planning_live.update(
                Panel("\n".join(planning_content), title="Planning", style="magenta")
            )

        return self._stream_final_answer(prompt, workspace, thread)

    def _stream_final_answer(self, prompt, workspace, thread):
        answer_question = prompt
        session = self.research_session
        inject_compare = should_inject_compare_prefetch(
            raw_prompt=prompt,
            is_follow_up=bool(self._resolved_turn and self._resolved_turn.is_follow_up),
        )
        if (
            session
            and len(session.query_tickers) >= 2
            and session.prefetched_market_block
            and inject_compare
        ):
            workspace.append(
                {
                    "role": "user",
                    "content": (
                        session.prefetched_market_block
                        + "\n\nInstruction: Write a complete side-by-side comparison "
                        f"for {', '.join(session.query_tickers)} using the data above. "
                        "Do not ask the user to retrieve missing tickers."
                    ),
                    "type": "data",
                }
            )
        elif session and session.prefetched_market_block:
            workspace.append(
                {
                    "role": "user",
                    "content": (
                        session.prefetched_market_block
                        + "\n\nInstruction: Use the prefetched market data above when "
                        "answering the user's latest question."
                    ),
                    "type": "data",
                }
            )
        answer_text = ""
        answer_spinner = Spinner(
            "dots", text="[bright_cyan]Answering...[/bright_cyan]"
        )
        with Live(answer_spinner, console=console, refresh_per_second=10):
            for chunk in self.agent.answer(answer_question, workspace):
                answer_text += chunk
        if not str(answer_text).strip():
            console.print(
                "[yellow]The model returned an empty answer. "
                "Try again, shorten the thread with /clear, or switch models in config.[/yellow]"
            )
            console.print()
        answer_text = clean_model_text(answer_text)
        if answer_text.strip():
            markdown_answer = Markdown(answer_text)
            console.print(
                Panel(markdown_answer, title="Response", border_style="cyan")
            )
        record_assistant_turn(
            thread,
            answer_text,
            raw_user_query=prompt,
            session_id=self._session_id(),
        )
        append_history_event(
            self.history_session,
            "final_answer",
            {"answer": answer_text},
        )

        tokens = self.token_counter.count_conversation_tokens(thread)
        thread_pct = int(self.token_budget.thread_utilization(tokens) * 100)
        thread_note = (
            f" | thread [yellow]{thread_pct}%[/yellow] of "
            f"{self.thread_max_tokens:,} cap"
            if thread_pct >= 75
            else f" | thread {tokens:,}/{self.thread_max_tokens:,}"
        )

        console.print(
            f"[dim white]Tokens used: [/dim white][white]{tokens:,}[/white]"
            f"{thread_note}"
            f" | [dim white]with [/dim white][magenta]♥[/magenta] "
            f"[dim white]by [/dim white][link=https://rallies.ai][dim white]rallies.ai[/dim white][/link]",
            justify="right",
        )
        if thread_pct >= 90:
            console.print(
                "[yellow]Thread is near its token cap — older turns are being dropped. "
                "Run /compact to summarize history.[/yellow]"
            )
        append_history_event(
            self.history_session,
            "turn_completed",
            {"tokens_used": tokens},
        )

        return answer_text
