import random
import tiktoken
import json
import os
import requests
from pathlib import Path
import yaml
from datetime import datetime, timezone
import uuid
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from .storage import Storage
from .sources.registry import extract_tickers

class TokenCounter:
    def __init__(self, model="gpt-4o"):
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self.encoding = tiktoken.get_encoding("o200k_base")
    
    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self.encoding.encode(text))
    
    def count_conversation_tokens(self, conversation: list) -> int:
        total_tokens = 0
        for message in conversation:
            if isinstance(message, dict) and "content" in message:
                total_tokens += self.count_tokens(message["content"])
            elif isinstance(message, str):
                total_tokens += self.count_tokens(message)
        return total_tokens
    
    def format_token_count(self, token_count: int) -> str:
        if token_count >= 1000:
            return f"{token_count / 1000:.1f}k tokens"
        return f"{token_count} tokens"

def get_timeout_message(elapsed_time):
    """Get appropriate message based on elapsed time"""
    
    if elapsed_time < 10:
        return "[yellow]  Retrieving data...[/yellow]"
    else:
         # After retrieving data, randomly pick from these messages every 10 seconds
        messages = [
                "[yellow]  Cogitating...[/yellow]",
                "[yellow]  Deep dive...[/yellow]",
                "[yellow]  Percolating...[/yellow]",
                "[yellow]  Synthesizing...[/yellow]",
                "[yellow]  Triangulating...[/yellow]",
                "[yellow]  Crystallizing...[/yellow]",
                "[yellow]  Distilling...[/yellow]",
                "[yellow]  Calibrating...[/yellow]",
                "[yellow]  Optimizing...[/yellow]",
                "[yellow]  Finalizing...[/yellow]",
                "[yellow]  Polishing...[/yellow]",
                "[yellow]  Contemplating...[/yellow]",
                "[yellow]  Deliberating...[/yellow]",
                "[yellow]  Ruminating...[/yellow]",
                "[yellow]  Pondering...[/yellow]",
                "[yellow]  Mulling over...[/yellow]",
                "[yellow]  Reflecting...[/yellow]",
                "[yellow]  Meditating...[/yellow]",
                "[yellow]  Concentrating...[/yellow]",
                "[yellow]  Focusing...[/yellow]",
                "[yellow]  Absorbing...[/yellow]",
                "[yellow]  Digesting...[/yellow]",
                "[yellow]  Assimilating...[/yellow]",
                "[yellow]  Integrating...[/yellow]",
                "[yellow]  Harmonizing...[/yellow]",
                "[yellow]  Balancing...[/yellow]",
                "[yellow]  Aligning...[/yellow]",
                "[yellow]  Orchestrating...[/yellow]",
                "[yellow]  Weaving...[/yellow]",
                "[yellow]  Crafting...[/yellow]",
                "[yellow]  Sculpting...[/yellow]",
                "[yellow]  Refining...[/yellow]",
        ]
        # Change message every 10 seconds after initial retrieval
        message_index = int((elapsed_time - 10) // 10) % len(messages)
        return messages[message_index]

def show_help(console):
    from rich.table import Table
    from rich.columns import Columns

    console.print("\n[bright_cyan]Available Commands[/bright_cyan]")

    categories = {
        "Screener": [
            ("/screen [criteria]", "Multi-agent stock screener (e.g. /screen tech value, /screen growth healthcare)"),
            ("/screen sector=tech style=value", "Structured params: sector, style, min_mcap, max_pe"),
        ],
        "Compound commands": [
            ("/compound_help", "Guide: combine commands on one line (/ask … /watchlist)"),
        ],
        "Research observability": [
            ("/rules", "Show user research rules (.rallies/RULES.md)"),
            ("/soul", "Show tone overlay (.rallies/SOUL.md)"),
            ("/graph-status", "LangGraph checkpoint debug (thread id, tickers, last node)"),
            ("/research-log", "Show last scratchpad JSONL path and recent entries"),
            ("/fetch URL", "Fetch URL → markdown (IR pages, cached)"),
            ("/bundle TICKER", "Parallel quote + SEC (diagnostic)"),
            ("/skill [NAME]", "List or load SKILL.md workflows"),
            ("/memo TICKER long|short", "Investment memo → .rallies/memos/ HTML"),
            ("/filing TICKER [section]", "SEC filing section via edgartools"),
            ("/research QUERY", "Tool loop with skills; bare /research shows deep-dive example"),
        ],
        "Personas (Advanced)": [
            ("/personas", "List all 37 AI agent personas"),
            ("/ask PERSONA Q", "Ask a persona (e.g. /ask buffett NVDA)"),
            ("/debate A vs B Q", "Debate between two personas"),
            ("/consensus $TICKER ...", "7-category panel ($AMZN $META … or compound /watchlist)"),
        ],
        "Quant (Advanced)": [
            ("/dcf TICKER [g] [r]", "DCF valuation (e.g. /dcf NVDA)"),
            ("/optimize [risk 1-10] [TICKERS]", "Rebalance portfolio (holdings + sector limits)"),
            ("/options TICKER", "Options chain with Black-Scholes"),
            ("/analysis TICKER", "Quant analysis (Sharpe, Sortino, drawdown)"),
            ("/chart TICKER [5y ...]", "Valuation dashboard in browser + optional LLM summary"),
            ("/chart AAPL MSFT", "Compare tickers in browser (multi-ticker)"),
        ],
        "Data": [
            ("/quote TICKER", "Real-time price, P/E, market cap"),
            ("/financials TICKER", "Multi-year income statement"),
            ("/sec TICKER [FORM]", "SEC filings (8-K, 10-K, 10-Q)"),
            ("/earnings TICKER", "Earnings dates & surprises"),
            ("/earnings", "Upcoming earnings calendar"),
            ("/news TICKER", "Latest headlines & sources"),
            ("/peers TICKER", "Peer company comparison"),
            ("/index NAME", "SP500, NASDAQ, DJI snapshot"),
            ("/vix", "Volatility Index (VIX)"),
            ("/searchsec QUERY", "Search SEC filings by keyword"),
        ],
        "Analysis": [
            ("/insider TICKER", "Recent insider trades (Form 4)"),
            ("/holdings TICKER", "Top institutional holders"),
            ("/macro", "Economic dashboard (Fed, CPI, GDP)"),
            ("/hedgefund", "Hedge fund leverage & positioning"),
            ("/sector NAME", "Sector overview (tech, energy, etc.)"),
        ],
        "Portfolio": [
            ("/tickers list [PREFIX]", "Browse catalog (← → pages of 10); $ autocomplete"),
            ("/watchlist", "Default watchlist (list / add / remove)"),
            ("/watchlist NAME", "Named watchlist (e.g. watchlist_khan)"),
            ("/watchlist NAME TICKER", "Add ticker to named list (shorthand)"),
            ("/watchlist watchlists", "List all watchlist names"),
            ("/portfolio", "Default portfolio (list / add / remove)"),
            ("/portfolio NAME", "Named portfolio (e.g. portfolio_2025)"),
            ("/portfolio NAME add T QTY PRICE", "Add to a named portfolio"),
            ("/portfolio portfolios", "List all portfolio names"),
            ("/alert TICKER %", "Set price alert"),
            ("/alerts", "Check triggered alerts"),
        ],
        "System": [
            ("/key API_KEY", "Set OpenRouter API key"),
            ("/history", "Saved session files"),
            ("/export [PATH]", "Save conversation to markdown (default: ~/.rallies/exports/)"),
            ("/resume PATH", "Reload conversation from an export file"),
            ("/clear", "Clear conversation"),
            ("/compact", "Compact conversation"),
            ("/example [topic]", "Example prompts"),
            ("/exit / quit", "Exit REPL"),
            ("/help", "Show this screen"),
        ],
    }

    for cat_name, cmds in categories.items():
        table = Table(title=None, show_header=False, box=None, padding=(0, 2, 0, 0))
        table.add_column("Cmd", style="bright_green", no_wrap=True)
        table.add_column("Description", style="dim")
        for cmd, desc in cmds:
            table.add_row(f"{cmd:35s}", desc)
        console.print(f"\n[bold]{cat_name}[/bold]")
        console.print(table)

    console.print()


def handle_help_command(console):
    show_help(console)
    return True


def handle_compound_help_command(console):
    from .compound import show_compound_help

    return show_compound_help(console)


def handle_export_command(prompt, conversation, console):
    """Export current REPL conversation to a timestamped markdown file."""
    from pathlib import Path

    from .conversation_export import (
        export_conversation,
        get_exports_dir,
        normalize_messages,
    )

    parts = prompt.strip().split(None, 1)
    dest = None
    if len(parts) > 1:
        dest = Path(parts[1].strip())

    try:
        path = export_conversation(conversation, dest=dest)
    except ValueError as e:
        console.print(f"[yellow]{e}[/yellow]")
        console.print(
            "[dim]Run a few queries first, then /export. "
            f"Default folder: {get_exports_dir()}[/dim]"
        )
        return True

    n = len(normalize_messages(conversation))
    console.print(f"[green]Conversation exported[/green] ({n} message(s))")
    console.print(f"[white]{path}[/white]")
    console.print(f"[dim]Resume later:[/dim] /resume {path}")
    return True


def handle_resume_command(prompt, conversation, console):
    """Restore conversation from a markdown file created by /export."""
    from pathlib import Path

    from .conversation_export import get_exports_dir, resume_conversation

    parts = prompt.strip().split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        console.print(
            "[yellow]Usage: /resume PATH[/yellow]\n"
            "[dim]Example: /resume ~/.rallies/exports/chat_2026-06-02_143052.md[/dim]\n"
            f"[dim]Exports folder:[/dim] {get_exports_dir()}"
        )
        return True

    path = Path(parts[1].strip()).expanduser()
    if not path.is_file():
        console.print(f"[red]File not found:[/red] {path}")
        console.print(f"[dim]Look in {get_exports_dir()}[/dim]")
        return True

    try:
        meta = resume_conversation(conversation, path)
    except (ValueError, OSError) as e:
        console.print(f"[red]Could not resume:[/red] {e}")
        return True

    n = len(conversation)
    exported = meta.get("exported_at") or "unknown"
    console.print(
        f"[green]Conversation resumed[/green] — {n} message(s) loaded from export."
    )
    console.print(f"[dim]Originally exported:[/dim] {exported}")
    console.print(
        "[dim]Continue asking questions; the model will use this thread as context.[/dim]"
    )
    return True


def _manager_session_id(manager) -> str | None:
    if manager is None:
        return None
    history = getattr(manager, "history_session", None)
    if isinstance(history, dict):
        return str(history.get("id") or "") or None
    return None


def _begin_llm_command(conversation: list | None, manager, prompt: str) -> None:
    """
    Persist the slash-command query at turn start (write-only).

    Commands run in isolation — they do not load prior chat into their LLM calls.
    Follow-up free-form questions load the saved pairs via build_thread_context().
    """
    from .thread_memory import record_user_query

    record_user_query(prompt.strip(), session_id=_manager_session_id(manager))


def _strip_rich_markup(text: str) -> str:
    """Plain text for session memory (screener tables use Rich markup)."""
    import re

    plain = re.sub(r"\[/?[^\]]+\]", "", str(text or ""))
    for ch in "│┃":
        plain = plain.replace(ch, "|")
    return re.sub(r"\n{3,}", "\n\n", plain).strip()


def _record_llm_command_turn(
    conversation: list,
    manager,
    *,
    user_query: str,
    assistant_answer: str,
    console=None,
    followup_context: dict | None = None,
) -> None:
    from .followup_suggestions import (
        build_followup_questions,
        print_followup_questions_panel,
    )
    from .thread_memory import record_command_turn

    record_command_turn(
        conversation,
        user_query=user_query,
        assistant_answer=assistant_answer,
        session_id=_manager_session_id(manager),
    )
    if console is not None:
        ctx = dict(followup_context or {})
        if "command" not in ctx and user_query.strip().startswith("/"):
            ctx["command"] = user_query.strip().split(None, 1)[0].lower()
        questions = build_followup_questions(**ctx)
        print_followup_questions_panel(console, questions)


def handle_clear_command(conversation, console, manager=None):
    from .thread_memory import clear_session_memory

    session_id = None
    if manager is not None:
        history = getattr(manager, "history_session", None)
        if isinstance(history, dict):
            session_id = str(history.get("id") or "") or None
    clear_session_memory(conversation, session_id=session_id)
    if manager is not None:
        manager.history_session = create_history_session()
        append_history_event(
            manager.history_session,
            "session_started",
            {"tier": getattr(manager, "tier", "free"), "reason": "clear"},
        )
    console.print("[green]Conversation history cleared.[/green]")
    return True


def handle_compact_command(prompt, conversation, agent, console):
    if len(conversation) == 0:
        console.print("[red]No conversation history to compact.[/red]")
        return True
    
    console.print("Let us compact the conversation to reduce tokens")
    compacted = agent.compact(conversation)
    conversation[:] = compacted
    tokens = TokenCounter().count_conversation_tokens(conversation)
    console.print(f"[green]✓ Conversation condensed to {tokens} tokens. You can continue asking more questions now.[/green]")
    console.print()
    return True 


def handle_exit_command(console):
    console.print("\nGoodbye!")
    import sys
    sys.exit(0)


def get_config_dir():
    """Get or create the rallies data directory (same root as checkpoints/scratchpad)."""
    from .research.paths import rallies_data_dir

    config_dir = rallies_data_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file():
    """Get the config file path"""
    return get_config_dir() / "config.json"


def get_history_dir():
    """Get or create the history directory."""
    history_dir = get_config_dir() / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir


def get_active_chat_session_file():
    """Path to persisted chat session id for LangGraph turn-pair memory."""
    return get_config_dir() / "active_chat_session.json"


def save_active_chat_session(session: dict) -> None:
    """Persist session id so the next CLI launch can resume turn-pair memory."""
    if not isinstance(session, dict):
        return
    session_id = str(session.get("id") or "").strip()
    if not session_id:
        return
    payload = {
        "id": session_id,
        "started_at": session.get("started_at"),
        "file_path": session.get("file_path"),
    }
    path = get_active_chat_session_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_active_chat_session() -> dict | None:
    path = get_active_chat_session_file()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict) and str(data.get("id") or "").strip():
        return data
    return None


def _new_history_session_record() -> dict:
    started_at = datetime.now(timezone.utc)
    day_dir = get_history_dir() / started_at.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    session_id = started_at.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    file_path = day_dir / f"{session_id}.jsonl"
    return {
        "id": session_id,
        "started_at": started_at.isoformat(),
        "file_path": str(file_path),
    }


def _init_session_memory_file(session: dict) -> None:
    from .graph.flags import turn_pair_memory_enabled
    from .memory.file_store import ensure_session_memory_file

    if not turn_pair_memory_enabled():
        return
    session_id = str(session.get("id") or "").strip()
    if not session_id:
        return
    ensure_session_memory_file(
        session_id,
        started_at=str(session.get("started_at") or "") or None,
    )


def create_history_session(*, persist_active: bool = True) -> dict:
    """Create a new structured history session file."""
    session = _new_history_session_record()
    _init_session_memory_file(session)
    if persist_active:
        save_active_chat_session(session)
    return session


def load_or_create_history_session() -> dict:
    """
    Start a fresh chat session for each CLI launch.

    Turn-pair memory is scoped to this session id for the current run only.
    Use /clear to reset mid-session; use /resume PATH to reload an export.
    """
    return create_history_session()


def append_history_event(session, event_type, payload):
    """Append a structured event to session history file."""
    if not session:
        return
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": payload,
    }
    file_path = Path(session["file_path"])
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=True) + "\n")


def log_turn_aborted(session, reason, detail=None, **extra):
    """Record that the current user turn did not finish with turn_completed."""
    if not session:
        return
    payload = {"reason": reason}
    if detail:
        payload["detail"] = str(detail)[:4000]
    for key, val in extra.items():
        if val is not None:
            payload[key] = val
    append_history_event(session, "turn_aborted", payload)


def log_session_ended(session, reason, detail=None, phase=None):
    """Record why the CLI session is ending (e.g. Ctrl+C)."""
    if not session:
        return
    payload = {"reason": reason}
    if detail:
        payload["detail"] = str(detail)[:4000]
    if phase:
        payload["phase"] = phase
    append_history_event(session, "session_ended", payload)


def list_recent_history_files(limit=20):
    """List recent history files for navigation."""
    history_dir = get_history_dir()
    files = sorted(
        history_dir.glob("**/*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[:limit]


def get_provider_config_file():
    """Get provider YAML config path."""
    config_override = os.getenv("RALLIES_PROVIDER_CONFIG")
    if config_override:
        return Path(config_override).expanduser()

    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "config" / "rallies-provider.yaml"


def load_config():
    """Load configuration from file"""
    config_file = get_config_file()
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def load_provider_config():
    """Load and validate provider configuration from YAML."""
    config_file = get_provider_config_file()
    if not config_file.exists():
        raise ValueError(
            f"Provider config not found at {config_file}. "
            "Create config/rallies-provider.yaml or set RALLIES_PROVIDER_CONFIG."
        )

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in provider config: {e}") from e
    except IOError as e:
        raise ValueError(f"Unable to read provider config: {e}") from e

    provider = raw.get("openrouter", {})
    required_fields = ["base_url", "model", "timeout_seconds", "api_key_env"]
    missing = [field for field in required_fields if not provider.get(field)]
    if missing:
        raise ValueError(
            "Missing required fields in openrouter config: "
            + ", ".join(missing)
        )

    return provider


def load_app_config():
    """Load full application config (sections beyond openrouter)."""
    config_file = get_provider_config_file()
    if not config_file.exists():
        return {}
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, IOError):
        return {}


def get_provider_api_key(provider_config):
    """Resolve provider API key from configured environment variable."""
    env_name = provider_config.get("api_key_env", "").strip()
    if not env_name:
        raise ValueError("Missing openrouter.api_key_env in provider config.")

    api_key = os.getenv(env_name)
    if api_key:
        return api_key

    config = load_config()
    saved_key = config.get("openrouter_api_key", "").strip()
    if saved_key:
        return saved_key

    raise ValueError(
        f"Missing API key. Export {env_name}=... or run /key <OPENROUTER_API_KEY>."
    )


def save_config(config):
    """Save configuration to file"""
    config_file = get_config_file()
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f)
        return True
    except IOError:
        return False


def get_api_key():
    """Get the stored API key"""
    config = load_config()
    return config.get("api_key")


def set_api_key(api_key):
    """Set and save the API key"""
    config = load_config()
    config["api_key"] = api_key
    return save_config(config)


def handle_key_command(prompt, agent, console):
    """Handle the /key command"""
    parts = prompt.strip().split(None, 1)
    if len(parts) < 2:
        console.print("[red]Usage: /key API_KEY[/red]")
        return True
    
    api_key = parts[1]
    config = load_config()
    config["openrouter_api_key"] = api_key
    config["api_key"] = api_key

    if save_config(config):
        if hasattr(agent, "set_api_key"):
            agent.set_api_key(api_key)
        else:
            agent.api_key = api_key
        console.print("[green]OpenRouter API key saved and activated.[/green]")
        console.print("[dim]Stored at ~/.rallies/config.json for future sessions.[/dim]")
    else:
        console.print("[red]Failed to save API key.[/red]")
    return True





def handle_history_command(console, manager):
    """Handle /history command."""
    files = list_recent_history_files(limit=20)
    if not files:
        console.print("[yellow]No history files found yet.[/yellow]")
        return True

    console.print("\n[bright_cyan]Recent history sessions:[/bright_cyan]")
    for i, file_path in enumerate(files, 1):
        modified = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"[white]{i:2}. {modified}[/white]  [dim]{file_path}[/dim]")

    if manager and getattr(manager, "history_session", None):
        console.print(
            f"\n[dim]Current session:[/dim] [white]{manager.history_session['id']}[/white]"
        )
        console.print(
            f"[dim]Current file:[/dim] [white]{manager.history_session['file_path']}[/white]"
        )
    console.print("[dim]Each line is JSON (JSONL) with timestamp, event_type, and payload.[/dim]\n")
    return True


def _ticker_from_parts(parts: list[str], index: int = 1) -> str | None:
    from .ticker_library import normalize_ticker_token

    if len(parts) <= index:
        return None
    return normalize_ticker_token(parts[index])


def handle_tickers_command(prompt: str, console) -> bool:
    """Manage the extensible ticker catalog (~/.rallies/tickers.json)."""
    from .ticker_library import (
        catalog_stats,
        user_add_ticker,
        user_remove_ticker,
        user_tickers_path,
    )

    parts = prompt.strip().split(None, 2)
    sub = parts[1].lower() if len(parts) > 1 else ""
    rest = parts[2] if len(parts) > 2 else ""

    if not sub:
        stats = catalog_stats()
        path = user_tickers_path()
        console.print("\n[bold cyan]Ticker library[/bold cyan]")
        console.print(f"[dim]Prefix tickers with $ in questions (e.g. $AAPL $MSFT). Tab completes after $.[/dim]\n")
        console.print(f"  Active symbols: [white]{stats['total']}[/white]")
        console.print(f"  Bundled:        [dim]{stats['builtin']}[/dim]")
        console.print(f"  Your additions: [dim]{stats['user_add']}[/dim]")
        console.print(f"  Your removals:  [dim]{stats['user_remove']}[/dim]")
        console.print(f"  Overrides file: [white]{path}[/white]\n")
        console.print(
            "[dim]/tickers list [PREFIX] — paginated (← →) · "
            "/tickers add SYM [name] · /tickers remove SYM[/dim]\n"
        )
        return True

    if sub == "path":
        console.print(f"[white]{user_tickers_path()}[/white]")
        return True

    if sub == "list":
        from .paginated_list import browse_rows_interactive
        from .ticker_library import filter_ticker_catalog

        prefix = rest.strip().upper()
        rows = filter_ticker_catalog(prefix)
        title = f"Tickers — {prefix}*" if prefix else "Tickers"
        browse_rows_interactive(rows, title=title)
        return True

    if sub == "add":
        tokens = rest.split(None, 1)
        if not tokens:
            console.print("[yellow]Usage: /tickers add SYMBOL [optional name][/yellow]")
            return True
        sym_token = tokens[0]
        name = tokens[1] if len(tokens) > 1 else ""
        try:
            entry = user_add_ticker(sym_token, name=name)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            return True
        console.print(f"[green]Added[/green] [white]{entry['symbol']}[/white] to your ticker library.")
        return True

    if sub == "remove":
        if not rest.strip():
            console.print("[yellow]Usage: /tickers remove SYMBOL[/yellow]")
            return True
        try:
            changed = user_remove_ticker(rest.split()[0])
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            return True
        if changed:
            console.print(f"[green]Removed[/green] [white]{rest.split()[0].upper().lstrip('$')}[/white] from your library.")
        else:
            console.print("[yellow]Symbol was not in your add/remove overrides.[/yellow]")
        return True

    console.print("[yellow]Usage: /tickers [list [PREFIX] | add SYM | remove SYM | path][/yellow]")
    return True


def handle_watch_command(prompt, console, storage):
    from .watchlist_names import DEFAULT_WATCHLIST, parse_watchlist_prompt

    try:
        watchlist_name, sub, args = parse_watchlist_prompt(prompt)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return True

    label = watchlist_name if watchlist_name != DEFAULT_WATCHLIST else "watchlist"

    if sub == "watchlists":
        names = storage.watchlist_list_names()
        if not names:
            console.print(
                "[yellow]No watchlists yet.[/yellow] "
                "[white]/watchlist watchlist_khan MU[/white]"
            )
            return True
        from rich.table import Table

        table = Table(title="Named watchlists", title_style="bold cyan")
        table.add_column("Name", style="bright_green")
        table.add_column("Tickers", justify="right")
        table.add_column("Created", style="dim")
        for row in names:
            table.add_row(
                row["name"],
                str(row["ticker_count"]),
                str(row.get("created_at") or ""),
            )
        console.print(table)
        console.print(
            "[dim]Default: /watchlist · Named: /watchlist NAME · "
            "Shorthand add: /watchlist watchlist_khan MU[/dim]"
        )
        return True

    if sub == "create":
        if not args.strip():
            console.print("[yellow]Usage: /watchlist create NAME[/yellow]")
            return True
        try:
            created = storage.watchlist_create(args.split()[0])
            console.print(f"[green]Created watchlist[/green] [white]{created}[/white]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
        return True

    if sub == "delete":
        if not args.strip():
            console.print("[yellow]Usage: /watchlist delete NAME[/yellow]")
            return True
        try:
            if storage.watchlist_delete(args.split()[0]):
                console.print(
                    f"[green]Deleted watchlist[/green] [white]{args.split()[0].lower()}[/white]"
                )
            else:
                console.print("[yellow]Watchlist not found.[/yellow]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
        return True

    if sub == "rename":
        parts_rename = args.split()
        if len(parts_rename) < 2:
            console.print("[yellow]Usage: /watchlist rename OLD_NAME NEW_NAME[/yellow]")
            return True
        try:
            new = storage.watchlist_rename(parts_rename[0], parts_rename[1])
            console.print(f"[green]Renamed to[/green] [white]{new}[/white]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
        return True

    if sub == "list":
        items = storage.watchlist_list(watchlist_name)
        if not items:
            console.print(
                f"[yellow]Watchlist '{watchlist_name}' is empty.[/yellow] "
                f"[white]/watchlist {label} add TICKER[/white] "
                f"[dim]or[/dim] [white]/watchlist {watchlist_name} MU[/white]"
            )
            return True

        # Auto-cleanup: split any legacy entries with commas into individual tickers
        cleaned = False
        for item in items:
            if "," in item["ticker"]:
                old_ticker = item["ticker"]
                tickers_to_add = [t.strip() for t in old_ticker.replace(",", " ").split() if t.strip()]
                for t in tickers_to_add:
                    if t.startswith("/"):
                        continue
                    storage.watchlist_add(t, watchlist_name=watchlist_name)
                storage.watchlist_remove(old_ticker, watchlist_name=watchlist_name)
                cleaned = True
        if cleaned:
            items = storage.watchlist_list(watchlist_name)
            console.print("[dim]Cleaned up legacy entries, re-fetching...[/dim]")

        # Also remove any stored invalid tickers (containing /)
        for item in items:
            if "/" in item["ticker"]:
                storage.watchlist_remove(item["ticker"], watchlist_name=watchlist_name)
                cleaned = True
        if cleaned:
            items = storage.watchlist_list(watchlist_name)

        if not items:
            console.print(f"[yellow]Watchlist '{watchlist_name}' is empty.[/yellow]")
            return True

        wl_title = (
            "Watchlist"
            if watchlist_name == DEFAULT_WATCHLIST
            else f"Watchlist — {watchlist_name}"
        )
        console.print(f"[yellow]Fetching fundamentals for {wl_title}...[/yellow]")
        try:
            import yfinance as yf
            import logging
            logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        except ImportError:
            console.print("[yellow]yfinance not available, showing basic list.[/yellow]")
            _show_watchlist_basic(items, console)
            return True

        from rich.table import Table
        from .metric_units import QUOTE_UNITS_NOTE, label as metric_label

        table = Table(
            title=f"{wl_title} ({len(items)} tickers)",
            title_style="bold cyan",
            caption=QUOTE_UNITS_NOTE,
        )
        table.add_column("Ticker", style="bright_green", no_wrap=True)
        table.add_column(metric_label("price"), justify="right")
        table.add_column(metric_label("market_cap"), justify="right")
        table.add_column(metric_label("pe_trailing"), justify="right")
        table.add_column(metric_label("pe_forward"), justify="right")
        table.add_column(metric_label("eps_trailing"), justify="right")
        table.add_column(metric_label("dividend_yield_pct"), justify="right")
        table.add_column(metric_label("fifty_two_week_range"), justify="right")
        table.add_column(metric_label("target_mean"), justify="right")
        table.add_column(metric_label("rating"), justify="center")
        table.add_column("News", style="dim")

        # Prepare a tiny helper to fetch the first news item for a ticker.
        def _first_news(ticker_obj):
            try:
                news_items = getattr(ticker_obj, "news", []) or []
                if not news_items:
                    return ""
                first = news_items[0]
                title = first.get("title", "")
                link = first.get("link", "")
                if not title:
                    return ""
                title = title[:65] + ("..." if len(title) > 65 else "")
                return f"{title} ({link})" if link else title
            except Exception:
                return ""

        watch_errors = []
        for item in items:
            ticker = item["ticker"]
            vals = {k: "—" for k in ["price", "pe", "fpe", "eps", "div", "mcap", "range", "target", "rating"]}
            news_str = ""
            try:
                t = yf.Ticker(ticker)
                news_str = _first_news(t)
                from .yfinance_metrics import info_snapshot

                info = t.info or {}
                snap = info_snapshot(info)
                if snap.get("price") is not None:
                    vals["price"] = f"${float(snap['price']):.2f}"
                mcap = snap.get("market_cap")
                if mcap:
                    if mcap >= 1e12:
                        vals["mcap"] = f"${mcap/1e12:.2f}T"
                    else:
                        vals["mcap"] = f"${mcap/1e9:.1f}B"
                if snap.get("pe_trailing") is not None:
                    vals["pe"] = f"{float(snap['pe_trailing']):.1f}"
                if snap.get("pe_forward") is not None:
                    vals["fpe"] = f"{float(snap['pe_forward']):.1f}"
                if snap.get("eps_trailing") is not None:
                    vals["eps"] = f"{float(snap['eps_trailing']):.2f}"
                if snap.get("dividend_yield_pct") is not None:
                    vals["div"] = f"{float(snap['dividend_yield_pct']):.2f}%"
                lo52 = info.get("fiftyTwoWeekLow")
                hi52 = info.get("fiftyTwoWeekHigh")
                if lo52 and hi52:
                    vals["range"] = f"${float(lo52):.0f}-${float(hi52):.0f}"
                lo = info.get("targetLowPrice")
                avg = info.get("targetMeanPrice")
                hi = info.get("targetHighPrice")
                parts_t = []
                if lo: parts_t.append(f"${float(lo):.0f}")
                if avg: parts_t.append(f"${float(avg):.0f}")
                if hi: parts_t.append(f"${float(hi):.0f}")
                if parts_t:
                    vals["target"] = " / ".join(parts_t)
                rec = info.get("recommendationKey", "")
                num = info.get("numberOfAnalystOpinions", 0)
                if rec:
                    r = rec.lower()

                    if r in ("buy", "strong_buy"):
                        vals["rating"] = f"[green]{rec.upper()}[/green]"
                    elif r in ("hold", "neutral"):
                        vals["rating"] = f"[yellow]{rec.upper()}[/yellow]"
                    elif r in ("sell", "strong_sell"):
                        vals["rating"] = f"[red]{rec.upper()}[/red]"
                    else:
                        vals["rating"] = rec.upper()
                    if num:
                        vals["rating"] += f"[dim]({num})[/dim]"
                # Use the helper defined earlier to extract a concise news line.
                try:
                    news_str = _first_news(t)
                except Exception as e:
                    watch_errors.append({"ticker": ticker, "stage": "news", "error": str(e)})
            except Exception as e:
                watch_errors.append(
                    {"ticker": ticker, "stage": "quote", "error": str(e)}
                )

            table.add_row(ticker, vals["price"], vals["mcap"], vals["pe"], vals["fpe"],
                          vals["eps"], vals["div"], vals["range"], vals["target"],
                          vals["rating"], news_str)

        console.print(table)
        if watch_errors:
            preview = ", ".join(
                f"{err['ticker']} ({err['stage']})"
                for err in watch_errors[:5]
            )
            console.print(
                f"[yellow]Some watchlist fields could not be fetched:[/yellow] {preview}"
            )
        return True

    if sub == "add":
        from .ticker_library import normalize_ticker_tokens

        raw = args.strip()
        if not raw:
            console.print(
                f"[yellow]Usage: /watchlist {label} add TICKER [TICKER...][/yellow]\n"
                f"[dim]Shorthand: /watchlist {watchlist_name} $MU[/dim]"
            )
            return True
        candidates = normalize_ticker_tokens(raw.replace(",", " "))
        tickers = [t for t in candidates if not t.startswith("/")]
        if len(candidates) != len(tickers):
            console.print(f"[dim]Skipped {len(candidates) - len(tickers)} invalid ticker(s)[/dim]")
        added = 0
        skipped = 0
        existing = {i["ticker"] for i in storage.watchlist_list(watchlist_name)}
        for ticker in tickers:
            if ticker in existing:
                skipped += 1
                continue
            if storage.watchlist_add(ticker, watchlist_name=watchlist_name):
                added += 1
        in_label = (
            f" to [white]{watchlist_name}[/white]"
            if watchlist_name != DEFAULT_WATCHLIST
            else ""
        )
        if added:
            console.print(f"[green]Added {added} ticker(s){in_label}.[/green]")
        if skipped:
            console.print(
                f"[yellow]{skipped} ticker(s) already in '{watchlist_name}', skipped.[/yellow]"
            )
        if not added and not skipped:
            console.print("[yellow]No new tickers to add.[/yellow]")
        return True

    if sub == "remove":
        from .ticker_library import normalize_ticker_tokens

        raw = args.strip()
        if not raw:
            console.print(
                f"[yellow]Usage: /watchlist {label} remove TICKER [TICKER...][/yellow]"
            )
            return True
        tickers = normalize_ticker_tokens(raw.replace(",", " "))
        removed = 0
        for ticker in tickers:
            if storage.watchlist_remove(ticker, watchlist_name=watchlist_name):
                removed += 1
        if removed:
            console.print(
                f"[green]Removed {removed} ticker(s) from[/green] "
                f"[white]{watchlist_name}[/white]."
            )
        else:
            console.print(
                f"[yellow]None of those tickers were in watchlist '{watchlist_name}'.[/yellow]"
            )
        return True

    console.print(
        "[red]Usage:[/red]\n"
        "  [white]/watchlist[/white] — default watchlist\n"
        "  [white]/watchlist add|remove TICKER ...[/white]\n"
        "  [white]/watchlist watchlist_khan[/white] — list named watchlist\n"
        "  [white]/watchlist watchlist_khan MU[/white] — add MU (shorthand)\n"
        "  [white]/watchlist watchlist_finance add AAPL MSFT[/white]\n"
        "  [white]/watchlist watchlists[/white] — list all names"
    )
    return True


def handle_quote_command(prompt, console, manager):
    parts = prompt.strip().split(None, 1)
    if len(parts) < 2:
        console.print("[red]Usage: /quote TICKER[/red]")
        return True
    ticker = _ticker_from_parts(parts)
    if not ticker:
        console.print("[red]Usage: /quote $TICKER[/red]")
        return True

    yfs = None
    if manager and hasattr(manager, "data_registry"):
        for s in manager.data_registry._sources:
            if s.name == "yfinance":
                yfs = s
                break

    if yfs is None:
        console.print("[yellow]yfinance not available. Install with: pip install rallies[sources][/yellow]")
        return True

    from rich.table import Table
    console.print(f"[yellow]Fetching quote for {ticker}...[/yellow]")
    data = yfs.get_quote(ticker)
    if not data or "error" in data:
        console.print(f"[red]Could not fetch quote for {ticker}: {data.get('error', 'unknown error') if data else 'source unavailable'}[/red]")
        return True

    from .metric_units import QUOTE_UNITS_NOTE, label as metric_label

    table = Table(
        title=f"{ticker} — {data.get('name', '')}",
        title_style="bold cyan",
        caption=QUOTE_UNITS_NOTE,
    )
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bright_green")
    for key, lbl in [
        ("price", "price"),
        ("prev_close", "prev_close"),
        ("change_pct", "change_1d_pct"),
        ("day_high", "day_high"),
        ("day_low", "day_low"),
        ("volume", "volume"),
        ("market_cap", "market_cap"),
        ("eps", "eps_trailing"),
        ("pe", "pe_trailing"),
        ("pe_forward", "pe_forward"),
        ("peg_5yr", "peg_5yr"),
        ("dividend_yield_pct", "dividend_yield_pct"),
        ("sector", "sector"),
    ]:
        label = metric_label(lbl) if lbl != "sector" else "Sector"
        val = data.get(key)
        if val is not None and val != "":
            if key == "market_cap" and isinstance(val, (int, float)):
                val = f"${val:,.0f}"
            elif key == "volume" and isinstance(val, (int, float)):
                val = f"{val:,}"
            elif key in ("price", "prev_close", "day_high", "day_low") and isinstance(val, (int, float)):
                val = f"${val:.2f}"
            elif key == "change_pct" and isinstance(val, (int, float)):
                val = f"{val:+.2f}%"
            elif key == "dividend_yield_pct" and isinstance(val, (int, float)):
                val = f"{val:.2f}%"
            elif key in ("pe", "pe_forward", "peg_5yr", "eps") and isinstance(val, (int, float)):
                val = f"{val:.2f}" if key == "eps" else f"{val:.1f}" if key in ("pe", "pe_forward") else f"{val:.2f}"
            table.add_row(label, str(val))
    console.print(table)
    return True


def handle_sec_command(prompt, console, manager):
    parts = prompt.strip().split(None, 2)
    if len(parts) < 2:
        console.print("[red]Usage: /sec TICKER [FORM][/red]")
        console.print("[dim]FORM defaults to 8-K. Common forms: 10-K, 10-Q, 8-K, 4[/dim]")
        return True
    ticker = parts[1].upper().strip()
    form = parts[2].upper().strip() if len(parts) > 2 else "8-K"

    edgar = _find_source(manager, "edgartools")
    if edgar is None:
        console.print("[yellow]edgartools not available. Install with: pip install rallies[sources][/yellow]")
        return True

    console.print(f"[yellow]Fetching recent {form} filings for {ticker}...[/yellow]")
    filings = edgar.get_recent_filings(ticker, form=form, count=5)
    if not filings or "error" in filings:
        console.print(f"[red]Could not fetch filings for {ticker}: {filings.get('error', 'unknown') if filings else 'source unavailable'}[/red]")
        return True

    from rich.table import Table
    table = Table(title=f"Recent {form} Filings — {ticker}", title_style="bold cyan")
    table.add_column("Date", style="dim")
    table.add_column("Form", style="bright_green")
    table.add_column("Description")
    for f in filings:
        table.add_row(str(f.get("date", "")), f.get("form", ""), (f.get("description") or "")[:80])
    console.print(table)
    return True


def _find_source(manager, name):
    if manager and hasattr(manager, "data_registry"):
        return manager.data_registry.get_source(name)
    return None


def handle_financials_command(prompt, console, manager):
    parts = prompt.strip().split(None, 1)
    if len(parts) < 2:
        console.print("[red]Usage: /financials TICKER[/red]")
        return True
    ticker = parts[1].upper().strip()

    yfs = _find_source(manager, "yfinance")
    if yfs is None:
        console.print("[yellow]yfinance not available. Install with: pip install rallies[sources][/yellow]")
        return True

    console.print(f"[yellow]Fetching financials for {ticker}...[/yellow]")
    data = yfs.get_financials(ticker)
    if not data or "error" in data:
        console.print(f"[red]Error: {data.get('error', 'unknown') if data else 'source unavailable'}[/red]")
        return True

    from rich.table import Table
    from .metric_units import FINANCIALS_UNITS_NOTE, label as metric_label

    name = next((r["values"] for r in data["rows"] if r["label"] == "Total Revenue"), ["N/A"])
    table = Table(
        title=f"{ticker} — Annual Income Statement",
        title_style="bold cyan",
        caption=FINANCIALS_UNITS_NOTE,
    )
    table.add_column("Metric", style="dim")
    for p in data["periods"]:
        table.add_column(p, justify="right", style="bright_green")

    for row in data["rows"]:
        vals = []
        for v in row["values"]:
            if v is None:
                vals.append("—")
            elif isinstance(v, float) and v >= 1e9:
                vals.append(f"${v/1e9:.2f}B")
            elif isinstance(v, float) and v >= 1e6:
                vals.append(f"${v/1e6:.1f}M")
            elif isinstance(v, float) and v < 100:
                vals.append(f"{v:.2f}")
            else:
                vals.append(str(v))
        row_label = row["label"]
        if row_label == "Earnings Per Share":
            row_label = metric_label("eps_fiscal")
        table.add_row(row_label, *vals)

    if data["rows"]:
        table.add_section()
        revenues = None
        net_incomes = None
        for r in data["rows"]:
            if r["label"] == "Total Revenue":
                revenues = r["values"]
            if r["label"] == "Net Income":
                net_incomes = r["values"]

        if revenues and len(revenues) >= 2:
            growth_vals = []
            for i in range(len(revenues)):
                if i >= len(revenues) - 1:
                    growth_vals.append("—")
                elif revenues[i] and revenues[i + 1] and revenues[i + 1] != 0:
                    g = (revenues[i] / revenues[i + 1] - 1) * 100
                    growth_vals.append(f"{g:+.1f}%")
                else:
                    growth_vals.append("—")
            table.add_row(metric_label("rev_growth_fiscal"), *growth_vals)

        if revenues and net_incomes:
            margin_vals = []
            for i in range(len(revenues)):
                if revenues[i] and net_incomes[i] and revenues[i] != 0:
                    m = (net_incomes[i] / revenues[i]) * 100
                    margin_vals.append(f"{m:.1f}%")
                else:
                    margin_vals.append("—")
            table.add_row(metric_label("net_margin_fiscal"), *margin_vals)

    console.print(table)
    return True


def handle_insider_command(prompt, console, manager):
    parts = prompt.strip().split(None, 1)
    if len(parts) < 2:
        console.print("[red]Usage: /insider TICKER[/red]")
        return True
    ticker = parts[1].upper().strip()

    edgar = _find_source(manager, "edgartools")
    if edgar is None:
        console.print("[yellow]edgartools not available. Install with: pip install rallies[sources][/yellow]")
        return True

    console.print(f"[yellow]Fetching recent insider trades for {ticker}...[/yellow]")
    trades = edgar.get_insider_trades(ticker)
    if not trades:
        console.print(f"[yellow]No insider trade data available for {ticker}.[/yellow]")
        return True

    from rich.table import Table
    table = Table(title=f"Recent Insider Trades — {ticker}", title_style="bold cyan")
    table.add_column("Date", style="dim")
    table.add_column("Insider", style="white")
    table.add_column("Type", style="bright_green")
    table.add_column("Shares", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Holding", justify="right")

    for t in trades:
        if "error" in t:
            console.print(f"[red]Error: {t['error']}[/red]")
            return True
        if "info" in t:
            console.print(f"[yellow]{t['info']}[/yellow]")
            return True
        shares = t.get("shares", "")
        if isinstance(shares, (int, float)):
            shares = f"{shares:,.0f}"
        price = t.get("price", "")
        if isinstance(price, (int, float)):
            price = f"${price:.2f}"
        holding = t.get("holding", "")
        if isinstance(holding, (int, float)):
            holding = f"{holding:,.0f}"
        txn_type = t.get("type", "")
        if "sell" in txn_type.lower():
            txn_type = f"[red]{txn_type}[/red]"
        elif "buy" in txn_type.lower() or "grant" in txn_type.lower():
            txn_type = f"[green]{txn_type}[/green]"
        table.add_row(
            str(t.get("date", "")),
            t.get("owner", ""),
            txn_type,
            str(shares),
            str(price),
            str(holding),
        )

    console.print(table)
    return True


def handle_macro_command(console, manager):
    fred = _find_source(manager, "fred")
    if fred is None or not fred.available:
        console.print("[yellow]FRED data requires an API key. Set FRED_API_KEY environment variable.[/yellow]")
        console.print("[dim]Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html[/dim]")
        return True

    console.print("[yellow]Fetching economic indicators...[/yellow]")
    result = fred.get_macro_summary()
    if not result or "error" in result:
        console.print(f"[red]Error fetching macro data: {result.get('error', 'unknown') if result else 'unknown'}[/red]")
        return True

    from rich.table import Table
    table = Table(title="Economic Dashboard", title_style="bold cyan")
    table.add_column("Indicator", style="dim")
    table.add_column("Value", justify="right", style="bright_green")
    table.add_column("Date", style="dim")
    table.add_column("Prev", justify="right")

    for sid in ["FEDFUNDS", "CPIAUCSL", "UNRATE", "DGS10", "DGS2", "T10Y2Y", "GDPC1", "SP500"]:
        entry = result.data.get(sid) if hasattr(result, "data") else result.get(sid)
        if not entry:
            continue
        val = entry.get("value", "")
        prev = entry.get("previous")
        prev_str = f"{prev:.2f}" if prev is not None else "—"
        if isinstance(val, float):
            if sid in ("GDPC1", "SP500"):
                val_str = f"{val:,.0f}"
            elif sid in ("CPIAUCSL",):
                val_str = f"{val:.1f}"
            else:
                val_str = f"{val:.2f}%"
        else:
            val_str = str(val)
        table.add_row(entry.get("label", sid), val_str, entry.get("date", ""), prev_str)

    console.print(table)
    return True


def handle_holdings_command(prompt, console, manager):
    parts = prompt.strip().split(None, 1)
    if len(parts) < 2:
        console.print("[red]Usage: /holdings TICKER[/red]")
        return True
    ticker = parts[1].upper().strip()

    console.print(f"[yellow]Fetching institutional holdings for {ticker}...[/yellow]")
    from rich.table import Table

    # Try yfinance first (shows top institutional holders of a stock)
    holdings_errors = []
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        inst = t.institutional_holders
        if inst is not None and not inst.empty:
            table = Table(title=f"Top Institutional Holders — {ticker}", title_style="bold cyan")
            table.add_column("Holder", style="white")
            table.add_column("Shares", justify="right")
            table.add_column("Value", justify="right")
            table.add_column("Date Reported", style="dim")
            for _, row in inst.head(15).iterrows():
                holder = row.get("Holder", "")
                shares = row.get("Shares", 0)
                val = row.get("Value", row.get("Market Value", 0))
                date = row.get("Date Reported", row.get("Date", ""))
                val_str = f"${float(val)/1e6:.1f}M" if val else ""
                shares_str = f"{int(shares):,}" if shares else ""
                date_str = str(date)[:10] if date else ""
                table.add_row(str(holder)[:50], shares_str, val_str, date_str)
            console.print(table)
            return True
    except Exception as e:
        holdings_errors.append(
            {"stage": "institutional_holders", "error": str(e)}
        )

    # Fallback: yfinance major holders
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        major = t.major_holders
        if major is not None and not major.empty:
            table = Table(title=f"Major Holders — {ticker}", title_style="bold cyan")
            table.add_column("Category", style="dim")
            table.add_column("Percentage", justify="right")
            for _, row in major.iterrows():
                pct = row.iloc[0] if hasattr(row, "iloc") else row[0]
                cat = row.iloc[1] if hasattr(row, "iloc") and len(row) > 1 else row[1] if len(row) > 1 else ""
                table.add_row(str(cat).strip() if cat else "", f"{float(pct):.1f}%" if pct else "")
            console.print(table)
            return True
    except Exception as e:
        holdings_errors.append({"stage": "major_holders", "error": str(e)})

    console.print(f"[yellow]No institutional holdings data available for {ticker} (not widely held by institutions).[yellow]")
    if holdings_errors:
        details = "; ".join(
            f"{item['stage']}: {item['error'][:120]}" for item in holdings_errors
        )
        console.print(f"[dim]Details: {details}[/dim]")
    return True


def handle_hedgefund_command(console, manager):
    hf = _find_source(manager, "hedgefund")
    if hf is None:
        console.print("[yellow]Hedge Fund Monitor unavailable.[/yellow]")
        return True

    console.print("[yellow]Fetching hedge fund data...[/yellow]")
    result = hf.get_snapshot()
    if not result:
        console.print("[yellow]No hedge fund data available.[/yellow]")
        return True

    from rich.table import Table
    data = result.data if hasattr(result, "data") else result
    table = Table(title="Hedge Fund Industry Snapshot", title_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right", style="bright_green")
    table.add_column("Period", style="dim")

    for mnemonic in ["FPF-ALLQHF_LEVERAGERATIO_GAVWMEAN", "FPF-ALLQHF_GAV_SUM", "FPF-ALLQHF_NAV_SUM", "FICC-SPONSORED_REPO_VOL"]:
        entry = data.get(mnemonic)
        if not entry:
            continue
        val = entry.get("value", "")
        if isinstance(val, float):
            if "REPO" in mnemonic:
                val_str = f"${val:,.0f}"
            elif val > 1e9:
                val_str = f"${val:,.0f}"
            else:
                val_str = f"{val:.2f}"
        else:
            val_str = str(val)
        table.add_row(entry.get("label", mnemonic), val_str, entry.get("date", ""))

    console.print(table)
    return True


def handle_alert_command(prompt, console, manager):
    parts = prompt.strip().split(None, 2)
    if len(parts) < 3:
        console.print("[red]Usage: /alert TICKER +/-%[/red]")
        console.print("[dim]Example: /alert AAPL +5  (alert when AAPL moves +5% from current)[/dim]")
        return True

    ticker = parts[1].upper().strip()
    try:
        threshold = float(parts[2].replace("%", ""))
    except ValueError:
        console.print("[red]Threshold must be a number (e.g. 5 or -3)[/red]")
        return True

    if not manager or not hasattr(manager, "storage"):
        console.print("[red]Storage not available.[/red]")
        return True

    yfs = _find_source(manager, "yfinance")
    if yfs is None:
        console.print("[yellow]yfinance not available for price checking.[/yellow]")
        return True

    data = yfs.get_quote(ticker)
    if not data or "error" in data:
        console.print(f"[red]Could not fetch current price for {ticker}.[/red]")
        return True

    current_price = data.get("price")
    if not current_price:
        console.print(f"[red]No price data for {ticker}.[/red]")
        return True

    alert_key = f"alert:{ticker}"
    manager.storage.cache_set(alert_key, {
        "ticker": ticker,
        "threshold_pct": threshold,
        "base_price": float(current_price),
        "direction": "up" if threshold > 0 else "down",
    }, ttl_seconds=86400 * 7)

    console.print(f"[green]Alert set:[/green] {ticker} at ${current_price}, notify on {'+' if threshold > 0 else ''}{threshold}% move")
    console.print("[dim]Check alerts with /alerts command[/dim]")
    return True


def handle_alerts_command(console, manager):
    if not manager or not hasattr(manager, "storage"):
        console.print("[red]Storage not available.[/red]")
        return True

    yfs = _find_source(manager, "yfinance")
    if yfs is None:
        console.print("[yellow]yfinance not available.[/yellow]")
        return True

    all_alert_keys = manager.storage.cache_keys("alert:")
    if not all_alert_keys:
        console.print("[yellow]No alerts set. Use /alert TICKER % to create one.[/yellow]")
        return True

    alerts = []
    for alert_key in all_alert_keys:
        stored = manager.storage.cache_get(alert_key)
        ticker = (stored or {}).get("ticker") or alert_key.split("alert:", 1)[-1].upper()
        data = yfs.get_quote(ticker)
        if stored and data and "error" not in data and data.get("price"):
            base = stored.get("base_price", 0)
            current = float(data["price"])
            if base > 0:
                change = (current / base - 1) * 100
                threshold = stored.get("threshold_pct", 0)
                triggered = (threshold > 0 and change >= threshold) or (threshold < 0 and change <= threshold)
                alerts.append({
                    "ticker": ticker,
                    "base": base,
                    "current": current,
                    "change": change,
                    "threshold": threshold,
                    "triggered": triggered,
                })

    if not alerts:
        console.print("[yellow]No alerts set. Use /alert TICKER % to create one.[/yellow]")
        return True

    from rich.table import Table
    table = Table(title="Price Alerts", title_style="bold cyan")
    table.add_column("Ticker", style="bright_green")
    table.add_column("Base", justify="right")
    table.add_column("Current", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Status")

    for a in alerts:
        status = "[green]TRIGGERED[/green]" if a["triggered"] else "[dim]watching[/dim]"
        table.add_row(
            a["ticker"],
            f"${a['base']:.2f}",
            f"${a['current']:.2f}",
            f"{a['change']:+.2f}%",
            f"{a['threshold']:+.0f}%",
            status,
        )
    console.print(table)
    return True


_SECTOR_TICKERS = {
    "technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA"],
    "tech": ["AAPL", "MSFT", "GOOGL", "META", "NVDA"],
    "finance": ["JPM", "GS", "BAC", "V", "MA"],
    "financial": ["JPM", "GS", "BAC", "V", "MA"],
    "healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK"],
    "health": ["JNJ", "UNH", "PFE", "ABBV", "MRK"],
    "energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "consumer": ["AMZN", "TSLA", "HD", "MCD", "NKE"],
    "retail": ["AMZN", "HD", "WMT", "COST", "TGT"],
    "semiconductor": ["NVDA", "AMD", "INTC", "TSM", "AVGO"],
    "semis": ["NVDA", "AMD", "INTC", "TSM", "AVGO"],
    "ai": ["NVDA", "AMD", "MSFT", "GOOGL", "META"],
    "defense": ["RTX", "LMT", "NOC", "GD", "BA"],
    "aviation": ["BA", "RTX", "LMT", "GE", "SPR"],
    "biotech": ["AMGN", "GILD", "REGN", "VRTX", "BIIB"],
    "pharma": ["PFE", "ABBV", "MRK", "JNJ", "LLY"],
    "media": ["META", "GOOGL", "DIS", "NFLX", "CMCSA"],
    "crypto": ["COIN", "MSTR", "RIOT", "MARA", "CLSK"],
    "space": ["RKLB", "ASTS", "GSAT", "LUNR", "RDW"],
}


def _show_watchlist_basic(items, console):
    from rich.table import Table
    table = Table(title="Watchlist", title_style="bold cyan")
    table.add_column("#", style="dim")
    table.add_column("Ticker", style="bright_green")
    table.add_column("Added", style="dim")
    table.add_column("Notes")
    for i, item in enumerate(items, 1):
        table.add_row(str(i), item["ticker"], item["added_at"][:10], item["notes"])
    console.print(table)


_INDEX_TICKERS = {
    "sp500": "^GSPC",
    "sp": "^GSPC",
    "nasdaq": "^IXIC",
    "ndx": "^NDX",
    "dji": "^DJI",
    "dow": "^DJI",
    "russell": "^RUT",
    "rut": "^RUT",
    "vix": "^VIX",
}


def handle_example_command(subject, console):
    examples = {
        "": [
            "Do a complete fundamental analysis of AAPL covering revenue trends, profit margins, ROIC, free cash flow, debt levels, and how each metric has trended over the last 3 years",
            "Compare MSFT and GOOGL side by side on revenue growth, operating margins, P/E ratio, earnings per share, market cap, and insider trading activity — which is the better investment right now based on fundamentals?",
            "Analyze NVDA in depth: revenue growth trajectory, gross margin trends, P/E valuation vs peers, insider buying or selling activity, institutional ownership changes, and what the macro environment means for semiconductor stocks",
            "Give me a complete macro economic overview: current Fed funds rate, CPI inflation, unemployment, GDP growth, 10-year treasury yield, and explain how each of these affects growth stocks vs value stocks right now",
            "Deep dive into TSLA: check latest financial statements, revenue growth, profit margins, P/E and forward P/E, analyst price targets (low/avg/high), recent insider trading activity, institutional holdings, and how macro risks like interest rates impact the stock",
            "Do a full comparison of these 5 AI-related stocks: NVDA, AMD, AVGO, MRVL, and MU. Compare their revenue growth, P/E ratios, profit margins, market caps, and analyst ratings. Also check insider trading and hedge fund positioning in the semiconductor sector",
            "What does the current hedge fund data tell us about large cap tech? Check hedge fund leverage ratios, gross exposure in tech, net assets under management trends, and what this means for retail investors holding tech stocks",
            "Analyze my watchlist portfolio risk: check each tickers P/E, debt levels, sector concentration, and overlay current macro conditions (interest rates, inflation, GDP) to identify which positions are most vulnerable to a macro shock",
            "Check insider trading activity across my watchlist — has there been any significant insider selling or buying at any of these companies in the last 90 days? Look at Form 4 filings and flag any unusual patterns",
        ],
        "fundamentals": [
            "Do a complete fundamental analysis of AAPL covering revenue, net income, gross margin, operating margin, ROIC, free cash flow, debt-to-equity, and how each metric has trended over the last 3 fiscal years",
            "Compare MSFT and GOOGL across every key fundamental metric: revenue growth rate, profit margins, P/E (trailing and forward), EPS growth, free cash flow yield, ROIC, debt levels, and dividend history — which has stronger fundamentals?",
            "Deep dive into NVDA financials: analyze the 4-year income statement, calculate revenue CAGR, gross margin trajectory, operating leverage, net income conversion, and compare valuation (P/E, P/S, EV/EBITDA) against peers AMD and INTC",
            "Analyze RKLB financial health: review revenue trajectory, backlog growth, gross margin improvement, cash burn rate, path to profitability, compare against space sector peers (ASTS, LUNR, RDW) and give a fundamental rating",
            "Screen my watchlist for the best fundamental value: rank every ticker by P/E ratio, revenue growth, profit margin, and debt-to-equity. Flag any that look overvalued or have deteriorating fundamentals based on the latest financial data",
        ],
        "macro": [
            "Give me a complete macro dashboard: current Fed funds rate and target range, CPI headline and core inflation, unemployment rate, GDP growth (nominal and real), 10-year and 2-year treasury yields, yield curve slope, consumer sentiment, and explain what this means for equity markets",
            "How do current interest rates (Fed funds at 3.64%, 10Y at 4.57%) affect different sectors? Analyze the impact on tech stocks, banks, real estate, and consumer discretionary. Which sectors are most vulnerable and which benefit?",
            "What does the current treasury yield curve tell us about recession risk? Check the 2Y-10Y spread, look at historical patterns, and assess whether the current macro environment supports continued equity market strength or signals a downturn ahead",
            "Analyze the inflation outlook: review latest CPI and PCE data, energy price trends, wage growth, and the Feds preferred inflation metrics. What is the probability of the Fed cutting rates this year based on the data?",
            "How exposed is my watchlist to macro risk? Overlay current interest rates, inflation, GDP growth, and unemployment data against each tickers sector, valuation, and debt profile to identify which holdings would be hit hardest by a recession",
        ],
        "insider": [
            "Check insider trading activity for NVDA — look at Form 4 filings for the last 90 days. Has any executive or director sold or bought shares? How many shares, at what price, and what percentage of their holdings? Also check if trades were part of a 10b5-1 plan",
            "Scan insider activity across my entire watchlist — flag any tickers where executives have been net selling more than $100K in the last quarter. Show the insider names, transaction dates, share counts, and prices for each flagged trade",
            "Compare insider sentiment at MSFT vs GOOGL: which company has more insider buying relative to selling? Look at number of transactions, total share volume, dollar value of trades, and whether any pattern emerges (e.g. CTO selling vs CEO buying)",
            "Check 13F institutional holdings for TSLA — who are the top 10 institutional holders? How many shares does each hold, what percentage of the company, and how has institutional ownership changed quarter over quarter?",
            "What are the largest hedge funds buying and selling in the tech sector? Check recent 13F filings and Form 4 insider activity across major tech names to identify any smart money trends",
        ],
        "sectors": [
            "Compare the semiconductor sector (NVDA, AMD, INTC, TSM, AVGO) vs the software sector (MSFT, ORCL, CRM, ADBE, NOW) — which sector has better revenue growth, profit margins, P/E valuations, and insider trading activity?",
            "Deep dive into the space sector: analyze RKLB, ASTS, LUNR, RDW, and GSAT. Compare each companys revenue, growth rate, cash position, debt, and path to profitability. Which has the strongest fundamentals?",
            "How is the AI sector valuation looking? Check NVDA, AMD, MSFT, GOOGL, META, and CRM — are they overvalued based on P/E, P/S, and PEG ratios? Factor in current revenue growth rates to assess whether the AI premium is justified",
            "Which sectors are hedge funds most positioned in right now? Check the Hedge Fund Monitor data for sector-level positioning, leverage, and fund flows. Are they bullish on tech, rotating to energy, or hedging with defensive sectors?",
            "Analyze the biotech sector: compare AMGN, GILD, REGN, VRTX, and BIIB on revenue growth, R&D spending as percentage of revenue, profit margins, pipeline value, and insider trading activity",
        ],
        "portfolio": [
            "Analyze my portfolio holdings by sector concentration and macro risk exposure. For each ticker, show its sector, P/E ratio, beta, debt levels, and how it would perform in a rising rate vs falling rate environment. Flag any dangerous concentration",
            "Check which stocks in my portfolio have the strongest fundamentals: rank by revenue growth, profit margins, ROIC, and P/E. Identify the top 3 strongest and bottom 3 weakest holdings with specific data backing each ranking",
            "Scan my entire portfolio for insider trading red flags — has any executive at my held companies sold shares in the last quarter? Show insider name, transaction date, shares sold, price, and percentage of position sold for each flag",
            "Run a macro stress test on my portfolio: given current interest rates at 3.64%, inflation at 3.5%, and GDP growth at 2%, which of my holdings are most vulnerable? Consider sector sensitivity, valuation levels, and debt exposure for each ticker",
            "Give me a complete portfolio health check: total value, sector allocation percentages, weighted P/E, weighted revenue growth, number of holdings with insider selling, macro risk score, and top 3 recommended actions to improve the portfolio",
        ],
        "quick": [
            "/quote AAPL — real-time stock price, P/E, market cap",
            "/financials AAPL — multi-year income statement with margins & growth",
            "/earnings MSFT — next earnings date and recent quarterly surprises",
            "/sector semiconductors — snapshot of NVDA, AMD, INTC, TSM",
            "/index SP500 — S&P 500 index level and daily change",
            "/macro — Fed rate, CPI, unemployment, GDP, treasury yields",
            "/hedgefund — hedge fund industry leverage and positioning",
            "/watchlist — your watchlist with fundamentals and news",
            "/alert NVDA +5 — set price alert for 5% move from current",
            "/alerts — check triggered alerts on your watchlist",
            "/portfolio — portfolio with live P&L across all holdings",
            "/news AAPL — latest headlines and news sources",
            "/peers IONQ — peer comparison table with fundamentals",
            "/insider NVDA — recent insider trades from Form 4 filings",
            "/holdings TSLA — top institutional holders",
            "/searchsec guidance cut — search SEC filings for keywords",
            "/vix — CBOE Volatility Index (VIX) snapshot",
            "/screen tech momentum — screen technology stocks for momentum",
            "/screen healthcare value — screen healthcare for undervalued picks",
            "/screen all growth — full universe growth screener",
            "# Advanced commands (set mode.level: advanced in config):",
            "/personas — list all 37 AI agent personas",
            "/ask buffett NVDA — ask Warren Buffett about NVDA",
            "/debate buffett vs lynch on MSFT — two investing legends debate",
            "/dcf NVDA 0.15 0.09 — DCF valuation with custom growth/WACC",
            "/optimize risk 3 — conservative rebalance of /portfolio holdings",
            "/optimize risk 8 AAPL,MSFT — aggressive; add names to universe",
            "/options NVDA — options chain with Black-Scholes pricing",
            "/analysis NVDA — quant analysis with Sharpe, Sortino, drawdown",
        ],
    }

    topics = examples.get(subject, examples[""])
    console.print(f"\n[bright_cyan]Example prompts — {subject or 'all topics'}:[/bright_cyan]")
    for ex in topics:
        console.print(f"  [dim]>[/dim] [white]{ex}[/white]")
    return True


def handle_sector_command(prompt, console, manager):
    parts = prompt.strip().split(None, 1)
    sector = parts[1].lower().strip() if len(parts) > 1 else ""
    tickers = _SECTOR_TICKERS.get(sector)
    if not tickers:
        available = ", ".join(sorted(set(k for k in _SECTOR_TICKERS if k != "tech" or True)))
        console.print(f"[red]Unknown sector '{sector}'[/red]")
        console.print(f"[dim]Available: {available}[/dim]")
        return True

    from rich.table import Table
    from .metric_units import QUOTE_UNITS_NOTE, label as metric_label

    yfs = _find_source(manager, "yfinance")
    table = Table(
        title=f"Sector: {sector.title()}",
        title_style="bold cyan",
        caption=QUOTE_UNITS_NOTE,
    )
    table.add_column("Ticker", style="bright_green")
    table.add_column(metric_label("price"), justify="right")
    table.add_column(metric_label("change_1d_pct"), justify="right")
    table.add_column(metric_label("market_cap"), justify="right")
    table.add_column(metric_label("pe_trailing"), justify="right")
    table.add_column(metric_label("pe_forward"), justify="right")
    table.add_column(metric_label("peg_5yr"), justify="right")

    for t in tickers:
        if yfs:
            data = yfs.get_quote(t)
            if data and "error" not in data:
                price = data.get("price")
                change = ""
                if data.get("change_pct") is not None:
                    pct = float(data["change_pct"])
                    change = f"{pct:+.2f}%" if abs(pct) < 100 else "+N/A"
                elif price and data.get("prev_close"):
                    pct = (float(price) / float(data["prev_close"]) - 1) * 100
                    change = f"{pct:+.2f}%" if abs(pct) < 100 else "+N/A"
                mcap = data.get("market_cap")
                mcap_str = f"${mcap/1e12:.2f}T" if mcap and mcap >= 1e12 else f"${mcap/1e9:.1f}B" if mcap else ""
                pe_str = f"{float(data['pe']):.1f}" if data.get("pe") is not None else ""
                fpe_str = (
                    f"{float(data['pe_forward']):.1f}"
                    if data.get("pe_forward") is not None
                    else ""
                )
                peg_str = (
                    f"{float(data['peg_5yr']):.2f}"
                    if data.get("peg_5yr") is not None
                    else ""
                )
                price_str = f"${float(price):.2f}" if price else ""
                table.add_row(t, price_str, change, mcap_str, pe_str, fpe_str, peg_str)
    console.print(table)
    return True


def handle_index_command(prompt, console, manager):
    parts = prompt.strip().split(None, 1)
    index = parts[1].lower().strip() if len(parts) > 1 else "sp500"
    yf_ticker = _INDEX_TICKERS.get(index)
    if not yf_ticker:
        available = ", ".join(_INDEX_TICKERS.keys())
        console.print(f"[red]Unknown index '{index}'[/red]")
        console.print(f"[dim]Available: {available}[/dim]")
        return True

    try:
        import yfinance as yf
        t = yf.Ticker(yf_ticker)
        info = t.info or {}
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
        high = info.get("regularMarketDayHigh") or info.get("dayHigh")
        low = info.get("regularMarketDayLow") or info.get("dayLow")
        change = ""
        if price and prev:
            pct = (float(price) / float(prev) - 1) * 100
            change = f"{pct:+.2f}%"

        from rich.table import Table
        name = info.get("shortName") or info.get("longName") or index.upper()
        table = Table(title=f"{name}", title_style="bold cyan")
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bright_green")
        if price:
            table.add_row("Price", f"${float(price):.2f}")
        if change:
            table.add_row("Change", change)
        if prev:
            table.add_row("Prev Close", f"${float(prev):.2f}")
        if high and low:
            table.add_row("Day Range", f"${float(low):.2f} — ${float(high):.2f}")
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching {index}: {e}[/red]")
    return True


def handle_earnings_command(prompt, console, manager):
    parts = prompt.strip().split(None, 1)
    if len(parts) < 2:
        console.print("[red]Usage: /earnings TICKER[/red]")
        return True
    ticker = parts[1].upper().strip()

    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        cal = t.calendar or {}
        earnings = t.quarterly_earnings
        info = t.info or {}

        from rich.table import Table
        from .metric_units import EARNINGS_UNITS_NOTE, label as metric_label

        name = info.get("longName") or ticker
        table = Table(
            title=f"Earnings — {name}",
            title_style="bold cyan",
            caption=EARNINGS_UNITS_NOTE,
        )
        table.add_column("Quarter", style="dim")
        table.add_column(metric_label("reported_eps"), justify="right")
        table.add_column(metric_label("eps_estimate"), justify="right")
        table.add_column(metric_label("surprise_pct"), justify="right")

        # Next earnings date
        earnings_date = None
        if isinstance(cal, dict):
            earnings_date = cal.get("Earnings Date") or cal.get("earningsDate")
        if earnings_date:
            if isinstance(earnings_date, (list, tuple)) and earnings_date:
                earnings_date = earnings_date[0]
            next_val = (
                str(earnings_date.date())
                if hasattr(earnings_date, "date")
                else str(earnings_date)
            )
            console.print(f"[dim]Next Earnings:[/dim] [white]{next_val}[/white]")

        # Prefer `get_earnings_history()` when available (more reliable than `quarterly_earnings`).
        try:
            hist = t.get_earnings_history()  # DataFrame indexed by quarter
        except Exception:
            hist = None

        rows_added = False
        if hist is not None and hasattr(hist, "empty") and not hist.empty:
            # yfinance columns: epsActual, epsEstimate, epsDifference, surprisePercent
            for idx, row in hist.iloc[:8].iterrows():
                q = str(idx)[:10] if hasattr(idx, "strftime") else str(idx)[:10] if idx else ""
                eps = row.get("epsActual", "")
                est = row.get("epsEstimate", "")
                surp = ""
                try:
                    from .yfinance_metrics import surprise_percent

                    sp = surprise_percent(row.get("surprisePercent"))
                    if sp is not None:
                        surp = f"{sp:+.1f}%"
                except Exception:
                    surp = ""
                table.add_row(
                    q,
                    f"{float(eps):.2f}" if eps not in ("", None) else "",
                    f"{float(est):.2f}" if est not in ("", None) else "",
                    surp,
                )
                rows_added = True

            # Simple text "plot": show latest surprise direction + bar magnitude.
            if len(hist) > 0:
                latest = hist.iloc[0]
                try:
                    from .yfinance_metrics import surprise_percent

                    sp = surprise_percent(latest.get("surprisePercent"))
                    if sp is not None:
                        mag = min(20, abs(sp) / 5.0)
                        bar = ("#" * int(mag)).ljust(20)
                        direction = "UP" if sp >= 0 else "DOWN"
                        console.print(f"[dim]EPS surprise: {direction} ({sp:+.1f}%)[/dim]")
                        console.print(f"[dim]{bar}[/dim]")
                except Exception:
                    pass

        if not rows_added and earnings is not None and hasattr(earnings, "empty") and not earnings.empty:
            for idx, row in earnings.iterrows():
                q = str(idx)[:10] if hasattr(idx, "strftime") else str(idx)[:10] if idx else ""
                eps = row.get("EPS") if hasattr(row, "get") else row.iloc[0] if hasattr(row, "iloc") else ""
                est = row.get("Estimate") if hasattr(row, "get") else row.iloc[1] if hasattr(row, "iloc") and len(row) > 1 else ""
                surp = ""
                if eps and est:
                    surp = f"{((eps/est)-1)*100:+.1f}%"
                if q:
                    table.add_row(q, f"{eps:.2f}" if eps else "", f"{est:.2f}" if est else "", surp)
                    rows_added = True
        elif not rows_added and info.get("earningsQuarterly"):
            for eq in info["earningsQuarterly"][:8]:
                q = eq.get("date", "")[:10] if isinstance(eq, dict) else ""
                eps = eq.get("actual", "") if isinstance(eq, dict) else ""
                est = eq.get("estimate", "") if isinstance(eq, dict) else ""
                surp = ""
                if eps and est:
                    surp = f"{((eps/est)-1)*100:+.1f}%"
                if q:
                    table.add_row(q, f"{eps:.2f}" if eps else "", f"{est:.2f}" if est else "", surp)
                    rows_added = True

        if not rows_added:
            console.print("[yellow]No quarterly EPS surprise data available from yfinance right now.[/yellow]")

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching earnings for {ticker}: {e}[/red]")
    return True


def _format_portfolio_quantity(quantity: float) -> str:
    """Format share quantity for display (supports fractional lots)."""
    q = float(quantity)
    if abs(q - round(q)) < 1e-9:
        return str(int(round(q)))
    return f"{q:.6f}".rstrip("0").rstrip(".")


def _render_portfolio_table(items, portfolio_name, console, manager):
    """Rich table for one named portfolio."""
    from rich.table import Table

    from .metric_units import PORTFOLIO_UNITS_NOTE, label as metric_label

    yfs = _find_source(manager, "yfinance")
    title = "Portfolio" if portfolio_name == "default" else f"Portfolio — {portfolio_name}"
    table = Table(
        title=title,
        title_style="bold cyan",
        caption=PORTFOLIO_UNITS_NOTE,
    )
    table.add_column("Ticker", style="bright_green")
    table.add_column(metric_label("quantity"), justify="right")
    table.add_column(metric_label("cost_basis"), justify="right")
    table.add_column(metric_label("total_cost"), justify="right")
    table.add_column(metric_label("price"), justify="right")
    table.add_column(metric_label("value"), justify="right")
    table.add_column(f"{metric_label('pl')} / {metric_label('pl_pct')}", justify="right")
    total_cost = 0
    total_value = 0
    unknown_quotes = []
    for item in items:
        price = None
        if yfs:
            d = yfs.get_quote(item["ticker"])
            if d and "error" not in d:
                price = d.get("price")
        cprice = float(price) if price else None
        cost = item["quantity"] * item["cost_basis"]
        value = item["quantity"] * cprice if cprice is not None else None
        total_cost += cost
        if value is not None:
            total_value += value
        else:
            unknown_quotes.append(item["ticker"])
        pl = (value - cost) if value is not None else None
        pl_pct = (pl / cost * 100) if (pl is not None and cost) else None
        if pl is None:
            pl_str = "—"
        elif pl >= 0:
            pl_str = f"[green]+${pl:,.2f} ({pl_pct:+.1f}%)[/green]"
        else:
            pl_str = f"[red]-${-pl:,.2f} ({pl_pct:+.1f}%)[/red]"
        table.add_row(
            item["ticker"],
            _format_portfolio_quantity(item["quantity"]),
            f"${item['cost_basis']:.2f}",
            f"${cost:,.2f}",
            f"${cprice:.2f}" if cprice is not None else "—",
            f"${value:,.2f}" if value is not None else "—",
            pl_str,
        )
    table.add_section()
    total_pl = total_value - total_cost
    total_pl_str = (
        f"[green]+${total_pl:,.2f}[/green]"
        if total_pl >= 0
        else f"[red]-${-total_pl:,.2f}[/red]"
    )
    table.add_row(
        "[bold]Total[/bold]",
        "",
        "",
        f"[bold]${total_cost:,.2f}[/bold]",
        "",
        f"[bold]${total_value:,.2f}[/bold]",
        total_pl_str,
    )
    console.print(table)
    if unknown_quotes:
        console.print(
            "[yellow]Missing live quotes for:[/yellow] "
            + ", ".join(sorted(set(unknown_quotes)))
            + " [dim](totals exclude these positions)[/dim]"
        )


def handle_portfolio_command(prompt, console, manager):
    if not manager or not hasattr(manager, "storage"):
        console.print("[red]Storage not available.[/red]")
        return True

    from .portfolio_names import DEFAULT_PORTFOLIO, parse_portfolio_prompt

    s = manager.storage
    try:
        portfolio_name, sub, args = parse_portfolio_prompt(prompt)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return True

    label = portfolio_name if portfolio_name != DEFAULT_PORTFOLIO else "portfolio"

    if sub == "portfolios":
        names = s.portfolio_list_names()
        if not names:
            console.print(
                "[yellow]No portfolios yet.[/yellow] "
                "[white]/portfolio portfolio_2025 add MU 1.5 876[/white]"
            )
            return True
        from rich.table import Table

        table = Table(title="Named portfolios", title_style="bold cyan")
        table.add_column("Name", style="bright_green")
        table.add_column("Positions", justify="right")
        table.add_column("Created", style="dim")
        for row in names:
            table.add_row(
                row["name"],
                str(row["position_count"]),
                str(row.get("created_at") or ""),
            )
        console.print(table)
        console.print(
            "[dim]Default holdings: /portfolio list · Named: "
            "/portfolio NAME list | add | remove[/dim]"
        )
        return True

    if sub == "create":
        if not args.strip():
            console.print("[yellow]Usage: /portfolio create NAME[/yellow]")
            return True
        try:
            created = s.portfolio_create(args.split()[0])
            console.print(f"[green]Created portfolio[/green] [white]{created}[/white]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
        return True

    if sub == "delete":
        if not args.strip():
            console.print("[yellow]Usage: /portfolio delete NAME[/yellow]")
            return True
        try:
            if s.portfolio_delete(args.split()[0]):
                console.print(
                    f"[green]Deleted portfolio[/green] [white]{args.split()[0].lower()}[/white]"
                )
            else:
                console.print("[yellow]Portfolio not found.[/yellow]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
        return True

    if sub == "rename":
        parts = args.split()
        if len(parts) < 2:
            console.print("[yellow]Usage: /portfolio rename OLD_NAME NEW_NAME[/yellow]")
            return True
        try:
            new = s.portfolio_rename(parts[0], parts[1])
            console.print(f"[green]Renamed to[/green] [white]{new}[/white]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
        return True

    if sub == "list" or sub == "portfolio":
        items = s.portfolio_list(portfolio_name)
        if not items:
            console.print(
                f"[yellow]Portfolio '{portfolio_name}' is empty.[/yellow] "
                f"[white]/portfolio {portfolio_name} add TICKER QTY AVG_PRICE[/white] "
                "[dim](avg cost per share; e.g. MSFT 1.15 421)[/dim]"
            )
            return True
        _render_portfolio_table(items, portfolio_name, console, manager)
        return True

    if sub == "add":
        raw = args.strip()
        entries = [e.strip() for e in raw.replace(",", " ").split() if e.strip()]

        def _try_add_triple(ticker: str, qty_s: str, price_s: str) -> dict | None:
            try:
                qty = float(qty_s.rstrip(","))
                price = float(price_s.rstrip(","))
            except ValueError:
                return None
            if qty <= 0:
                return None
            symbol = ticker.upper().rstrip(",")
            result = s.portfolio_add(
                symbol, qty, price, portfolio_name=portfolio_name
            )
            return {"ticker": symbol, "qty": qty, "price": price, **result}

        added_rows: list[dict] = []

        if ":" in raw:
            for entry in entries:
                entry = entry.rstrip(",")
                if ":" not in entry:
                    continue
                parts_e = entry.split(":")
                row = _try_add_triple(parts_e[0], parts_e[1], parts_e[2])
                if row:
                    added_rows.append(row)
        elif len(entries) >= 3 and len(entries) % 3 == 0:
            for i in range(0, len(entries), 3):
                row = _try_add_triple(entries[i], entries[i + 1], entries[i + 2])
                if row:
                    added_rows.append(row)
        elif len(entries) >= 3:
            row = _try_add_triple(entries[0], entries[1], entries[2])
            if row:
                added_rows.append(row)

        def _print_add_result(row: dict) -> None:
            sym = row["ticker"]
            qty_s = _format_portfolio_quantity(row["qty"])
            price_s = f"${row['price']:.2f}"
            in_label = f" in [white]{portfolio_name}[/white]" if portfolio_name != DEFAULT_PORTFOLIO else ""
            if row.get("replaced") and row.get("previous"):
                prev = row["previous"]
                prev_qty = _format_portfolio_quantity(prev["quantity"])
                console.print(
                    f"[green]Updated {sym}{in_label}:[/green] {qty_s} shares @ {price_s} avg "
                    f"[dim](replaced {prev_qty} @ ${prev['cost_basis']:.2f} avg)[/dim]"
                )
            else:
                console.print(
                    f"[green]Added {sym}{in_label}:[/green] {qty_s} shares @ {price_s} avg"
                )

        if len(added_rows) == 1:
            _print_add_result(added_rows[0])
        elif added_rows:
            for row in added_rows:
                _print_add_result(row)
            updated = sum(1 for r in added_rows if r.get("replaced"))
            console.print(
                f"[dim]{len(added_rows)} position(s) saved in {portfolio_name}"
                + (f" ({updated} updated)" if updated else "")
                + f". Each ticker appears once in /portfolio {portfolio_name}.[/dim]"
            )
        else:
            console.print(
                f"[yellow]Usage: /portfolio {label} add TICKER QTY AVG_PRICE[/yellow]\n"
                "[dim]Default: /portfolio add MSFT 1.15 421[/dim]\n"
                "[dim]Named:  /portfolio portfolio_2025 add MU 1.5 876[/dim]\n"
                "[dim]Many:   /portfolio portfolio_khan add AAPL 10 150 MSFT 0.5 420[/dim]"
            )
        return True

    if sub == "remove":
        raw = args.upper().strip()
        if not raw:
            console.print(
                f"[yellow]Usage: /portfolio {label} remove TICKER [TICKER...][/yellow]"
            )
            return True
        tickers = [t.strip().rstrip(",") for t in raw.replace(",", " ").split() if t.strip()]
        removed = 0
        for ticker in tickers:
            if s.portfolio_remove(ticker, portfolio_name=portfolio_name):
                removed += 1
        if removed:
            console.print(
                f"[green]Removed {removed} ticker(s) from[/green] "
                f"[white]{portfolio_name}[/white]."
            )
        else:
            console.print(
                f"[yellow]None of those tickers were in portfolio '{portfolio_name}'.[/yellow]"
            )
        return True

    console.print(
        "[red]Usage:[/red]\n"
        "  [white]/portfolio[/white] — default portfolio (list)\n"
        "  [white]/portfolio add|remove|list ...[/white] — default portfolio\n"
        "  [white]/portfolio portfolio_2025[/white] — list named portfolio\n"
        "  [white]/portfolio portfolio_2025 add MU 1.5 876[/white]\n"
        "  [white]/portfolio portfolios[/white] — list all portfolio names\n"
        "  [white]/portfolio create|delete|rename NAME[/white]"
    )
    return True


def handle_news_command(prompt, console, manager):
    parts = prompt.strip().split(None, 1)
    if len(parts) < 2:
        console.print("[red]Usage: /news TICKER[/red]")
        return True
    ticker = parts[1].upper().strip()
    finnhub = _find_source(manager, "finnhub")
    if finnhub is None or not finnhub.available:
        console.print("[yellow]Finnhub API key not set. Set FINNHUB_API_KEY environment variable.[/yellow]")
        return True
    console.print(f"[yellow]Fetching news for {ticker}...[/yellow]")
    result = finnhub.get_company_news(ticker, max_items=5)
    if not result:
        console.print(f"[yellow]No news data available for {ticker}.[/yellow]")
        return True

    from rich.table import Table
    data = result.data
    table = Table(title=f"Latest News — {ticker}", title_style="bold cyan")
    table.add_column("Date", style="dim")
    table.add_column("Source", style="dim")
    table.add_column("Headline", style="white")
    for art in data.get("headlines", []):
        table.add_row(art.get("date", ""), art.get("source", ""), art.get("headline", "")[:90])
    console.print(table)
    return True


def handle_peers_command(prompt, console, manager):
    parts = prompt.strip().split(None, 1)
    if len(parts) < 2:
        console.print("[red]Usage: /peers TICKER[/red]")
        return True
    ticker = parts[1].upper().strip()
    finnhub = _find_source(manager, "finnhub")
    if finnhub is None or not finnhub.available:
        console.print("[yellow]Finnhub not configured.[/yellow]")
        return True
    console.print(f"[yellow]Finding peers for {ticker}...[/yellow]")
    result = finnhub.get_peers(ticker)
    if not result:
        console.print(f"[yellow]No peer data for {ticker}.[/yellow]")
        return True
    peers = result.data.get("peers", [])[:8]
    all_tickers = [ticker] + [p for p in peers if p != ticker]

    yfs = _find_source(manager, "yfinance")
    from rich.table import Table
    from .metric_units import PEERS_UNITS_NOTE, label as metric_label

    table = Table(
        title=f"Peer Comparison — {ticker}",
        title_style="bold cyan",
        caption=PEERS_UNITS_NOTE,
    )
    table.add_column("Ticker", style="bright_green", no_wrap=True)
    table.add_column(metric_label("price"), justify="right")
    table.add_column(metric_label("pe_trailing"), justify="right")
    table.add_column(metric_label("pe_forward"), justify="right")
    table.add_column(metric_label("market_cap"), justify="right")
    table.add_column(metric_label("peg_5yr"), justify="right")
    table.add_column(metric_label("revenue_growth_pct"), justify="right")
    table.add_column(metric_label("profit_margin_pct"), justify="right")

    for t in all_tickers[:9]:
        row = [t]
        if yfs:
            try:
                import yfinance as yf
                from .yfinance_metrics import info_snapshot

                snap = info_snapshot(yf.Ticker(t).info or {})
                row.append(
                    f"${float(snap['price']):.2f}" if snap.get("price") else "—"
                )
                row.append(
                    f"{float(snap['pe_trailing']):.1f}"
                    if snap.get("pe_trailing") is not None
                    else "—"
                )
                row.append(
                    f"{float(snap['pe_forward']):.1f}"
                    if snap.get("pe_forward") is not None
                    else "—"
                )
                mcap = snap.get("market_cap")
                cap = float(mcap) if mcap else 0
                if cap >= 1e12:
                    row.append(f"${cap/1e12:.2f}T")
                elif cap >= 1e9:
                    row.append(f"${cap/1e9:.1f}B")
                else:
                    row.append("—")
                row.append(
                    f"{float(snap['peg_5yr']):.2f}"
                    if snap.get("peg_5yr") is not None
                    else "—"
                )
                row.append(
                    f"{float(snap['revenue_growth_pct']):+.1f}%"
                    if snap.get("revenue_growth_pct") is not None
                    else "—"
                )
                row.append(
                    f"{float(snap['profit_margin_pct']):.1f}%"
                    if snap.get("profit_margin_pct") is not None
                    else "—"
                )
            except Exception:
                row.extend(["—"] * 7)
        else:
            row.extend(["—"] * 7)
        table.add_row(*row)

    console.print(table)
    return True
    return True


def handle_vix_command(console, manager):
    cboe = _find_source(manager, "cboe")
    if cboe is None:
        console.print("[yellow]CBOE source unavailable.[/yellow]")
        return True
    console.print("[yellow]Fetching VIX...[/yellow]")
    result = cboe.get_vix()
    if not result:
        console.print("[yellow]Could not fetch VIX data.[/yellow]")
        return True
    from rich.table import Table
    d = result.data
    table = Table(title="CBOE Volatility Index (VIX)", title_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bright_green")
    for key, label in [("vix", "VIX"), ("change", "Change"), ("change_pct", "Change %"), ("high", "Day High"), ("low", "Day Low")]:
        val = d.get(key, "")
        if val:
            table.add_row(label, f"{val:.2f}" if isinstance(val, (int, float)) else str(val))
    console.print(table)
    return True


def handle_searchsec_command(prompt, console, manager):
    parts = prompt.strip().split(None, 1)
    if len(parts) < 2:
        console.print("[red]Usage: /searchsec KEYWORDS[/red]")
        console.print("[dim]Search SEC filings for keywords (e.g. 'guidance cut', 'investigation', 'restructuring')[/dim]")
        return True
    query = parts[1].strip()
    sec = _find_source(manager, "sec")
    if sec is None:
        console.print("[yellow]SEC source unavailable.[/yellow]")
        return True
    console.print(f"[yellow]Searching SEC filings for '{query}'...[/yellow]")
    result = sec.search_filings(query)
    if not result:
        console.print("[yellow]No results found or SEC search unavailable.[/yellow]")
        return True
    results = result.data.get("results", [])
    if not results:
        console.print("[yellow]No filings found matching your query in the last 90 days.[/yellow]")
        return True
    from rich.table import Table
    table = Table(title=f"SEC Filings — \"{query}\"", title_style="bold cyan")
    table.add_column("Date", style="dim")
    table.add_column("Ticker", style="bright_green")
    table.add_column("Form", style="white")
    table.add_column("Description", style="dim")
    for r in results[:10]:
        table.add_row(r.get("date", ""), r.get("ticker", ""), r.get("form", ""), (r.get("description", "") or "")[:120])
    console.print(table)
    return True


def handle_earnings_calendar_command(console, manager):
    finnhub = _find_source(manager, "finnhub")
    if finnhub is None or not finnhub.available:
        console.print("[yellow]Finnhub not configured. Set FINNHUB_API_KEY.[/yellow]")
        return True
    console.print("[yellow]Fetching earnings calendar...[/yellow]")
    result = finnhub.get_earnings_calendar()
    if not result:
        console.print("[yellow]Could not fetch earnings calendar.[/yellow]")
        return True
    earnings = result.data.get("earnings", [])
    if not earnings:
        console.print("[yellow]No upcoming earnings in the next 14 days.[/yellow]")
        return True
    from rich.table import Table
    table = Table(title="Upcoming Earnings (Next 14 Days)", title_style="bold cyan")
    table.add_column("Date", style="dim")
    table.add_column("Ticker", style="bright_green")
    table.add_column("Quarter", justify="center")
    table.add_column("EPS Est.", justify="right")
    table.add_column("Hour", justify="center")
    for e in earnings[:15]:
        table.add_row(e.get("date", ""), e.get("ticker", ""),
                      f"Q{e.get('quarter', '')}" if e.get('quarter') else "",
                      str(e.get("estimate", "")), e.get("hour", ""))
    console.print(table)
    return True


def _get_mode_level():
    cfg = load_app_config()
    return cfg.get("mode", {}).get("level", "basic")


def _require_advanced(console) -> bool:
    mode = _get_mode_level()
    if mode != "advanced":
        console.print("[yellow]This command requires advanced mode. Set `mode.level: advanced` in config/rallies-provider.yaml[/yellow]")
        return False
    return True


def handle_rules_command(console):
    from .research import load_rules, rules_path, ensure_default_rules_template

    ensure_default_rules_template()
    path = rules_path()
    rules = load_rules()
    console.print(f"[bold cyan]Research rules[/bold cyan] [dim]({path})[/dim]\n")
    if rules:
        console.print(Panel(rules, border_style="cyan"))
    else:
        console.print(
            "[yellow]No rules yet. Edit the file above to guide research behavior.[/yellow]"
        )
    return True


def handle_research_log_command(console, manager=None):
    session = getattr(manager, "research_session", None) if manager else None
    if session is None:
        from .research import scratchpad_dir

        console.print(
            "[yellow]No active research session. Run a query or /ask, "
            "or open .rallies/scratchpad/[/yellow]"
        )
        sp = scratchpad_dir()
        files = sorted(sp.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            console.print(f"[dim]Latest:[/dim] {files[0]}")
            for line in files[0].read_text(encoding="utf-8").splitlines()[-5:]:
                console.print(f"[dim]{line[:220]}[/dim]")
        return True

    console.print(f"[bold cyan]Research log[/bold cyan]\n[dim]{session.filepath}[/dim]\n")
    for line in session.scratchpad.tail_lines(10):
        console.print(f"[dim]{line[:240]}[/dim]")
    return True


def handle_ask_command(prompt: str, agent, console, manager=None, conversation=None):
    if not _require_advanced(console):
        return True
    parts = prompt.strip().split(None, 2)
    if len(parts) < 3:
        console.print("[yellow]Usage: /ask PERSONA your question[/yellow]")
        console.print("[yellow]Example: /ask buffett should I buy NVDA?[/yellow]")
        return True
    persona_key = parts[1].lower()
    question = parts[2]
    compound_ctx = (
        getattr(manager, "compound_context", None) if manager is not None else None
    )
    try:
        from .advanced import ask_persona, PERSONAS
        from .research import ResearchSession

        if persona_key not in PERSONAS:
            console.print(f"[red]Unknown persona: {persona_key}. Use /personas to list available.[/red]")
            return True
        p = PERSONAS[persona_key]
        console.print(f"\n[bold cyan]🧠 {p['name']}[/bold cyan] [dim]({p['style']})[/dim]")
        console.print(f"[dim]\"{p['quote']}\"[/dim]\n")

        from .advanced.persona_market import (
            build_persona_live_data_block,
            format_persona_live_data_prefix,
            resolve_persona_tickers,
        )

        from .compound.limits import PERSONA_INLINE_TICKER_MAX

        compound_full_scope = bool(
            compound_ctx
            and (compound_ctx.tickers or compound_ctx.live_data_block)
        )
        if compound_ctx and compound_ctx.tickers:
            question = (
                f"{question}\n\nTickers in scope: {', '.join(compound_ctx.tickers)}."
            )
        elif compound_ctx and compound_ctx.live_data_block:
            question = (
                f"{question}\n\n(Portfolio/watchlist context attached — see live data block.)"
            )

        if conversation is not None:
            _begin_llm_command(conversation, manager, prompt.strip())

        session = ResearchSession.begin(f"/ask {persona_key}: {question}")
        session.query_tickers = resolve_persona_tickers(
            question,
            compound_ctx.tickers if compound_ctx else None,
            max_tickers=None if compound_full_scope else PERSONA_INLINE_TICKER_MAX,
        )
        if manager is not None:
            manager.research_session = session
            agent.set_research_session(session)
            agent.set_user_query(f"/ask {persona_key}: {question}")
        live_block = ""
        if compound_ctx and compound_ctx.live_data_block:
            console.print(
                f"[dim]Using compound context ({', '.join(compound_ctx.sources)})…[/dim]"
            )
            live_block = format_persona_live_data_prefix(compound_ctx.live_data_block)
        elif session.query_tickers:
            console.print(
                f"[dim]Prefetching live data for {', '.join(session.query_tickers)}...[/dim]"
            )
            live_block = build_persona_live_data_block(
                session.query_tickers,
                max_tickers=None if compound_full_scope else PERSONA_INLINE_TICKER_MAX,
                agent=agent,
                research_session=session,
            )
        elif manager and getattr(manager, "data_registry", None):
            console.print(
                "[dim]No ticker detected in question — answer uses persona lens only.[/dim]"
            )
        try:
            explicit = (
                list(compound_ctx.tickers)
                if compound_full_scope
                else session.query_tickers
            )
            result = ask_persona(
                persona_key,
                question,
                agent.llm,
                task_type="action",
                research_session=session,
                live_data_block=live_block if live_block else None,
                agent=agent,
                explicit_tickers=explicit,
            )
            console.print(Panel(Markdown(str(result)), title="Response", border_style="cyan"))
            console.print(f"[dim]Research log: {session.filepath}[/dim]")
            session.scratchpad.drain_warnings()
            if conversation is not None:
                _record_llm_command_turn(
                    conversation,
                    manager,
                    user_query=prompt.strip(),
                    assistant_answer=str(result),
                    console=console,
                    followup_context={
                        "command": "/ask",
                        "persona_name": p["name"],
                        "tickers": list(session.query_tickers),
                        "user_prompt": prompt.strip(),
                    },
                )
        finally:
            if manager is not None:
                manager.research_session = None
                agent.set_research_session(None)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
    return True


def handle_debate_command(prompt: str, agent, console, manager=None, conversation=None):
    if not _require_advanced(console):
        return True
    import re
    match = re.match(r"/debate\s+(\w+)\s+vs\s+(\w+)\s+(.+)", prompt.strip(), re.IGNORECASE)
    if not match:
        console.print("[yellow]Usage: /debate PERSONA_A vs PERSONA_B question[/yellow]")
        console.print("[yellow]Example: /debate buffett vs lynch is NVDA a buy?[/yellow]")
        return True
    persona_a = match.group(1).lower()
    persona_b = match.group(2).lower()
    question = match.group(3)
    try:
        from .advanced import debate_personas, PERSONAS
        if persona_a not in PERSONAS:
            console.print(f"[red]Unknown persona: {persona_a}[/red]")
            return True
        if persona_b not in PERSONAS:
            console.print(f"[red]Unknown persona: {persona_b}[/red]")
            return True
        pa = PERSONAS[persona_a]
        pb = PERSONAS[persona_b]
        from .advanced.persona_market import (
            build_persona_live_data_block,
            resolve_persona_tickers,
        )
        from .research import ResearchSession

        console.print(f"\n[bold cyan]📢 Debate: {pa['name']} vs {pb['name']}[/bold cyan]")
        console.print(f"[dim]Question: {question}[/dim]\n")

        compound_ctx = (
            getattr(manager, "compound_context", None) if manager is not None else None
        )
        from .compound.limits import PERSONA_INLINE_TICKER_MAX

        compound_full_scope = bool(
            compound_ctx
            and (compound_ctx.tickers or compound_ctx.live_data_block)
        )
        if compound_ctx and compound_ctx.tickers:
            question = (
                f"{question}\n\nTickers in scope: {', '.join(compound_ctx.tickers)}."
            )
        elif compound_ctx and compound_ctx.live_data_block:
            question = (
                f"{question}\n\n(Portfolio/watchlist context attached — see live data block.)"
            )

        if conversation is not None:
            _begin_llm_command(conversation, manager, prompt.strip())

        session = ResearchSession.begin(
            f"/debate {persona_a} vs {persona_b}: {question}"
        )
        session.query_tickers = resolve_persona_tickers(
            question,
            compound_ctx.tickers if compound_ctx else None,
            max_tickers=None if compound_full_scope else PERSONA_INLINE_TICKER_MAX,
        )
        if manager is not None:
            manager.research_session = session
        agent.set_research_session(session)
        agent.set_user_query(session.query)
        live_block = None
        if compound_ctx and compound_ctx.live_data_block:
            from .advanced.persona_market import format_persona_live_data_prefix

            console.print(
                f"[dim]Using compound context ({', '.join(compound_ctx.sources)})…[/dim]"
            )
            live_block = format_persona_live_data_prefix(compound_ctx.live_data_block)
        elif session.query_tickers:
            console.print(
                f"[dim]Prefetching live data for {', '.join(session.query_tickers)}...[/dim]"
            )
            live_block = build_persona_live_data_block(
                session.query_tickers,
                max_tickers=None if compound_full_scope else PERSONA_INLINE_TICKER_MAX,
                agent=agent,
                research_session=session,
            )
        try:
            response_a, response_b, name_a, name_b = debate_personas(
                persona_a,
                persona_b,
                question,
                agent.llm,
                live_data_block=live_block,
                agent=agent,
                research_session=session,
            )
        finally:
            agent.set_research_session(None)
            if manager is not None:
                manager.research_session = None
        console.print(Panel(Markdown(str(response_a)), title=str(name_a), border_style="cyan"))
        console.print(Panel(Markdown(str(response_b)), title=str(name_b), border_style="cyan"))
        if conversation is not None:
            combined = (
                f"**{name_a}**\n{response_a}\n\n**{name_b}**\n{response_b}"
            )
            _record_llm_command_turn(
                conversation,
                manager,
                user_query=prompt.strip(),
                assistant_answer=combined,
                console=console,
                followup_context={
                    "command": "/debate",
                    "persona_a": str(name_a),
                    "persona_b": str(name_b),
                    "tickers": list(session.query_tickers),
                    "user_prompt": prompt.strip(),
                },
            )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
    return True


def handle_personas_command(console):
    try:
        from .advanced import list_personas_by_category
        cats = list_personas_by_category()
        console.print("[bold cyan]Available Agent Personas[/bold cyan]\n")
        for cat, personas in cats.items():
            console.print(f"[bold]{cat}[/bold] ({len(personas)}):")
            for p in personas:
                console.print(f"  [white]{p['key']}[/white] — {p['name']} [dim]({p['style']})[/dim]")
            console.print("")
        console.print("[dim]Usage: /ask PERSONA your question (live quote/financials when tickers detected)[/dim]")
        console.print("[dim]       /debate PERSONA_A vs PERSONA_B question (same prefetch)[/dim]")
        console.print("[dim]       /consensus TICKER [...] — 7 experts + live data prefetch[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
    return True


def handle_dcf_command(prompt: str, console, manager):
    from .storage import Storage
    storage = getattr(manager, "storage", None) if manager else Storage()

    parts = prompt.strip().split()
    ticker = parts[1].upper() if len(parts) > 1 else None
    if not ticker:
        console.print("[yellow]Usage: /dcf TICKER [growth_rate] [wacc]")
        console.print("[yellow]Example: /dcf NVDA 0.15 0.09  (or 15 9 for percent)[/yellow]")
        return True

    from .metric_units import normalize_rate_decimal

    growth_rate = normalize_rate_decimal(float(parts[2])) if len(parts) > 2 else 0.10
    wacc = normalize_rate_decimal(float(parts[3])) if len(parts) > 3 else 0.09

    try:
        from .quant import dcf_valuation
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")

        from .quant.dcf import fetch_free_cash_flow_yfinance

        fcf, fcf_source = fetch_free_cash_flow_yfinance(t)
        shares = info.get("sharesOutstanding")
        cash = info.get("totalCash", 0)
        debt = info.get("totalDebt", 0)

        if not fcf or fcf <= 0:
            line1 = f"[yellow]{ticker} has no positive free cash flow (FCF).[/yellow]"
            line2 = f"  [dim]This usually means the company is pre-profit or reinvesting heavily.[/dim]"
            line3 = ""
            line4 = "  [bold]Why DCF won't work here:[/bold]"
            line5 = "  DCF assumes a company generates cash it can return to shareholders."
            line6 = "  For pre-profit or high-investment companies, try alternative approaches:"
            line7 = f"    [bold]•[/bold] Comparable company analysis (/peers {ticker})"
            line8 = f"    [bold]•[/bold] Revenue-based valuation (/financials {ticker})"
            line9 = f"    [bold]•[/bold] Price/sales ratio (/quote {ticker})"
            line10 = f"    [bold]•[/bold] Check if analyst have target prices (/news {ticker})"
            if price:
                mcap_info = f"Current market cap is [white]${(shares or 0) * price / 1e9:.1f}B[/white] at ${price:.2f} per share."
                console.print(f"[bold]DCF Valuation — {ticker}[/bold]\n\n{line1}\n{line2}\n{line3}\n{line4}\n{line5}\n{line6}\n{line7}\n{line8}\n{line9}\n{line10}\n\n{mcap_info}")
            else:
                console.print(f"[bold]DCF Valuation — {ticker}[/bold]\n\n{line1}\n{line2}\n{line3}\n{line4}\n{line5}\n{line6}\n{line7}\n{line8}\n{line9}\n{line10}")
            return True

        fair_value, details = dcf_valuation(
            ticker=ticker,
            free_cash_flow=fcf,
            growth_rate=growth_rate,
            wacc=wacc,
            shares_outstanding=shares,
            cash_and_equivalents=cash,
            total_debt=debt,
            current_price=price,
            fcf_source=fcf_source,
        )
        console.print(details)
    except ImportError:
        console.print("[yellow]DCF requires yfinance and numpy. Install: pip install yfinance numpy[/yellow]")
    except Exception as e:
        console.print(f"[red]DCF error:[/red] {e}")
    return True


def handle_optimize_command(prompt: str, console, manager):
    from .quant.portfolio_optimize import (
        holdings_from_storage,
        parse_optimize_args,
        run_portfolio_optimization,
    )
    from .storage import Storage

    storage = getattr(manager, "storage", None) if manager else Storage()
    registry = getattr(manager, "data_registry", None) if manager else None
    risk_level, extra_tickers = parse_optimize_args(prompt)

    from .portfolio_names import extract_portfolio_name_from_text

    portfolio_name = extract_portfolio_name_from_text(prompt)
    holdings = holdings_from_storage(storage, portfolio_name)
    watchlist = storage.watchlist_list() if storage else []
    watch_tickers = [
        str(item["ticker"]).upper()
        for item in watchlist
        if item.get("ticker")
    ]
    extra_tickers = list(dict.fromkeys((extra_tickers or []) + watch_tickers))
    if not holdings and len(extra_tickers) < 2:
        console.print(
            "[yellow]Add holdings with [/yellow]"
            f"[white]/portfolio {portfolio_name} add TICKER QTY AVG_PRICE[/white] "
            "[yellow]or pass tickers:[/yellow] [white]/optimize risk 5 AAPL,MSFT,NVDA[/white]\n"
            "[dim]Risk 1 = low volatility & tight sector limits · "
            "10 = higher return focus · default risk 5[/dim]"
        )
        return True

    try:
        result = run_portfolio_optimization(
            holdings,
            risk_level=risk_level,
            candidate_tickers=extra_tickers or None,
            data_registry=registry,
        )
        console.print(result)
    except Exception as e:
        console.print(f"[red]Optimize error:[/red] {e}")
    return True


def handle_options_command(prompt: str, console, manager=None):
    parts = prompt.strip().split()
    ticker = parts[1].upper() if len(parts) > 1 else None
    if not ticker:
        console.print("[yellow]Usage: /options TICKER[/yellow]")
        console.print("[yellow]Example: /options NVDA[/yellow]")
        return True
    try:
        from .quant import price_options
        import yfinance as yf
        t = yf.Ticker(ticker)
        price = (t.info or {}).get("currentPrice") or (t.info or {}).get("regularMarketPrice") or 0
        result = price_options(ticker, price)
        console.print(result)
    except ImportError:
        console.print("[yellow]Options requires yfinance. Install: pip install yfinance[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
    return True


def handle_analysis_command(prompt: str, console, manager=None):
    parts = prompt.strip().split()
    ticker = parts[1].upper() if len(parts) > 1 else None
    if not ticker:
        console.print("[yellow]Usage: /analysis TICKER[/yellow]")
        console.print("[yellow]Example: /analysis NVDA[/yellow]")
        return True
    try:
        from .quant import quant_analysis
        result = quant_analysis(ticker)
        console.print(result)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
    return True


def handle_screen_command(
    prompt: str, agent, console, manager=None, conversation=None
):
    try:
        from .screener import ScreenerOrchestrator
        storage = getattr(manager, "storage", None) if manager else None
        cfg = load_app_config()
        final_count = 10
        if cfg:
            fc = cfg.get("screener", {}).get("max_results")
            if fc is not None:
                final_count = int(fc)
        if conversation is not None:
            _begin_llm_command(conversation, manager, prompt.strip())
        orch = ScreenerOrchestrator(agent, storage=storage, final_count=final_count)
        result = orch.screen(prompt, console=console)
        console.print(result)
        if conversation is not None and str(result).strip():
            plain_result = _strip_rich_markup(str(result))
            _record_llm_command_turn(
                conversation,
                manager,
                user_query=prompt.strip(),
                assistant_answer=plain_result,
                console=console,
                followup_context={
                    "command": "/screen",
                    "user_prompt": prompt.strip(),
                    "screen_text": plain_result,
                },
            )
    except ImportError as e:
        console.print(f"[red]Screener module unavailable: {e}[/red]")
        console.print("[yellow]Make sure yfinance is installed: pip install yfinance[/yellow]")
    except Exception as e:
        console.print(f"[red]Screener error:[/red] {e}")
    return True


def handle_command(prompt, conversation, agent, console, manager=None):
    from .compound import try_handle_compound_command

    if try_handle_compound_command(
        prompt, conversation, agent, console, manager=manager
    ):
        return True

    p = prompt.strip()

    if p == "/help":
        return handle_help_command(console)

    if p == "/compound_help":
        return handle_compound_help_command(console)
    
    if p == "/history":
        return handle_history_command(console, manager)

    if p == "/graph-status" or p.startswith("/graph-status"):
        from .graph.commands import handle_graph_status_command

        return handle_graph_status_command(console, manager)

    if p.startswith("/export"):
        return handle_export_command(prompt, conversation, console)

    if p.startswith("/resume"):
        return handle_resume_command(prompt, conversation, console)

    if p == "/clear":
        return handle_clear_command(conversation, console, manager=manager)
    
    if p.startswith("/compact"):
        return handle_compact_command(prompt, conversation, agent, console)
    
    if p.startswith("/key"):
        return handle_key_command(prompt, agent, console)

    if p.startswith("/tickers"):
        return handle_tickers_command(prompt, console)

    if p.startswith("/watch"):
        storage = getattr(manager, "storage", None) if manager else None
        if storage is None:
            storage = Storage()
        return handle_watch_command(prompt, console, storage)

    if p.startswith("/quote"):
        return handle_quote_command(prompt, console, manager)

    if p.startswith("/sec ") or p == "/sec":
        return handle_sec_command(prompt, console, manager)

    if p.startswith("/financials"):
        return handle_financials_command(prompt, console, manager)

    if p.startswith("/insider"):
        return handle_insider_command(prompt, console, manager)

    if p.startswith("/holdings"):
        return handle_holdings_command(prompt, console, manager)

    if p.startswith("/macro"):
        if p == "/macro":
            return handle_macro_command(console, manager)
        console.print("[yellow]Usage: /macro[/yellow]")
        return True

    if p.startswith("/hedgefund"):
        if p == "/hedgefund":
            return handle_hedgefund_command(console, manager)
        console.print("[yellow]Usage: /hedgefund[/yellow]")
        return True

    if p.startswith("/alert") and not p.startswith("/alerts"):
        return handle_alert_command(prompt, console, manager)

    if p.startswith("/alerts"):
        if p == "/alerts":
            return handle_alerts_command(console, manager)
        console.print("[yellow]Usage: /alerts[/yellow]")
        return True

    if p.startswith("/example"):
        parts = p.split(None, 1)
        subject = parts[1].lower().strip() if len(parts) > 1 else ""
        return handle_example_command(subject, console)

    if p.startswith("/sector"):
        return handle_sector_command(prompt, console, manager)

    if p.startswith("/index"):
        return handle_index_command(prompt, console, manager)

    if p.startswith("/portfolio"):
        return handle_portfolio_command(prompt, console, manager)

    if p.startswith("/news"):
        return handle_news_command(prompt, console, manager)

    if p.startswith("/peers"):
        return handle_peers_command(prompt, console, manager)

    if p.startswith("/vix"):
        if p == "/vix":
            return handle_vix_command(console, manager)
        console.print("[yellow]Usage: /vix[/yellow]")
        return True

    if p.startswith("/searchsec"):
        return handle_searchsec_command(prompt, console, manager)

    if p.startswith("/personas"):
        return handle_personas_command(console)

    if p == "/rules" or p.startswith("/rules "):
        return handle_rules_command(console)

    if p == "/soul" or p.startswith("/soul "):
        from .research.commands import handle_soul_command

        return handle_soul_command(console)

    if p.startswith("/fetch"):
        from .research.commands import handle_fetch_command

        return handle_fetch_command(prompt, console)

    if p.startswith("/bundle"):
        from .research.commands import handle_bundle_command

        return handle_bundle_command(prompt, console, manager)

    if p.startswith("/skill"):
        from .research.commands import handle_skill_command

        return handle_skill_command(prompt, console)

    if p.startswith("/filing"):
        from .research.commands import handle_filing_command

        return handle_filing_command(prompt, console, manager)

    if p.startswith("/research") and not p.startswith("/research-log"):
        from .research.commands import handle_research_command

        return handle_research_command(prompt, console, manager, agent, conversation)

    if p == "/research-log" or p.startswith("/research-log"):
        return handle_research_log_command(console, manager)

    if p.startswith("/memo"):
        from .research.commands import handle_memo_command

        return handle_memo_command(prompt, console, manager, agent)

    if p.startswith("/ask"):
        return handle_ask_command(
            prompt, agent, console, manager=manager, conversation=conversation
        )

    if p.startswith("/debate"):
        return handle_debate_command(
            prompt, agent, console, manager=manager, conversation=conversation
        )

    if p.startswith("/dcf"):
        return handle_dcf_command(prompt, console, manager)

    if p.startswith("/optimize"):
        return handle_optimize_command(prompt, console, manager)

    if p.startswith("/options"):
        return handle_options_command(prompt, console, manager)

    if p.startswith("/analysis"):
        return handle_analysis_command(prompt, console, manager)

    if p.startswith("/chart"):
        from .charts import handle_chart_command

        return handle_chart_command(prompt, console, agent=agent)

    if p.startswith("/screen"):
        return handle_screen_command(
            prompt, agent, console, manager=manager, conversation=conversation
        )

    if p.startswith("/consensus"):
        return handle_consensus_command(
            prompt, agent, console, manager, conversation=conversation
        )

    # /earnings TICKER (ticker-specific) or /earnings (calendar)
    if p.startswith("/earnings"):
        parts = p.split(None, 2)
        if len(parts) >= 2:
            return handle_earnings_command(prompt, console, manager)
        return handle_earnings_calendar_command(console, manager)

    if p in ["/exit", "/quit"]:
        handle_exit_command(console)

    if p.startswith("/"):
        console.print(f"[red]Unknown command:[/red] {p}")
        console.print("[yellow]Type /help to see available commands and usage examples.[/yellow]")
        return True

    return False


def handle_consensus_command(
    prompt: str, agent, console, manager=None, conversation=None
):
    """Multi-persona consensus: one expert per category, sequential analysis."""
    if not _require_advanced(console):
        return True

    parts = prompt.strip().split()
    if len(parts) < 2:
        console.print(
            "[yellow]Usage: /consensus $TICKER [$TICKER ...][/yellow]\n"
            "[dim]Example: /consensus $NVDA[/dim]\n"
            "[dim]         /consensus $AAPL $MSFT $GOOGL[/dim]\n"
            "[dim]         /consensus rank $AMZN $META $MSFT from best to worst[/dim]\n\n"
            "Runs one persona from each category in sequence (Value, Growth, Macro, "
            "Quant, Hedge Fund, Economic, Tech), then a consensus summary."
        )
        return True

    from .compound.limits import (
        CONSENSUS_BATCH_SIZE,
        chunk_consensus_batches,
        consensus_panel_ticker_order,
    )

    compound_ctx = (
        getattr(manager, "compound_context", None) if manager is not None else None
    )
    ranking_instruction = ""
    if compound_ctx and compound_ctx.tickers:
        tickers = list(compound_ctx.tickers)
    else:
        from .ticker_identify import parse_consensus_prompt

        tickers, ranking_instruction = parse_consensus_prompt(prompt)
    tickers = consensus_panel_ticker_order(tickers, compound_ctx)
    if not tickers:
        console.print(
            "[yellow]Usage: /consensus $TICKER [$TICKER ...][/yellow]\n"
            "[dim]Or: /consensus … /watchlist[/dim]"
        )
        return True

    try:
        from .advanced.consensus_batch import (
            needs_batched_consensus,
            run_batched_consensus_analysis,
        )
        from .advanced.personas import (
            format_batched_consensus_for_session_memory,
            format_consensus_for_session_memory,
            get_consensus_panel,
            run_consensus_analysis,
        )

        panel = get_consensus_panel()
        names = ", ".join(f"{p['name']}" for p in panel)
        cats = ", ".join(f"{p['category']}" for p in panel)
        batched = needs_batched_consensus(len(tickers))
        batches = chunk_consensus_batches(tickers, compound_ctx=compound_ctx)

        console.print(
            f"\n[bold cyan]Consensus Panel[/bold cyan] — "
            f"[white]{len(tickers)} ticker(s)[/white]"
        )
        if batched:
            console.print(
                f"[dim]{len(batches)} batches × up to {CONSENSUS_BATCH_SIZE} tickers "
                f"({len(panel)} experts + summary per batch)[/dim]"
            )
        console.print(f"[dim]Tickers: {', '.join(tickers)}[/dim]")
        console.print(
            f"[dim]Experts (random per category, shuffled order): {names}[/dim]"
        )
        console.print(f"[dim]Categories: {cats}[/dim]\n")

        if conversation is not None:
            _begin_llm_command(conversation, manager, prompt.strip())

        data_registry = getattr(manager, "data_registry", None) if manager else None

        def _print_verdict_matrix(panel_results, batch_tickers, title_suffix=""):
            table = Table(
                title=f"Verdict Matrix{title_suffix} — {', '.join(batch_tickers)}",
                title_style="bold cyan",
            )
            table.add_column("Expert", style="white")
            table.add_column("Category", style="dim")
            for ticker in batch_tickers:
                table.add_column(ticker, justify="center")

            for entry in panel_results:
                if entry.get("error"):
                    table.add_row(
                        entry.get("name", "?"),
                        entry.get("category", ""),
                        *["ERROR"] * len(batch_tickers),
                    )
                    continue
                cells = [
                    entry.get("tickers", {}).get(ticker, {}).get("verdict", "—")
                    for ticker in batch_tickers
                ]
                table.add_row(entry.get("name", "?"), entry.get("category", ""), *cells)
            console.print(table)

        def on_persona_complete(result, idx, total, batch_tickers=None):
            active = batch_tickers if batch_tickers is not None else tickers
            name = result.get("name", result.get("key", "?"))
            category = result.get("category", "")
            if result.get("error"):
                console.print(f"[red]  [{idx}/{total}] {name} — {result['error']}[/red]")
                return
            console.print(f"[green]  [{idx}/{total}] {name}[/green] [dim]({category})[/dim]")
            for ticker in active:
                tdata = result.get("tickers", {}).get(ticker, {})
                if not tdata:
                    continue
                verdict = tdata.get("verdict", "—")
                conf = tdata.get("confidence", "")
                console.print(
                    f"      [white]{ticker}[/white]: [bold]{verdict}[/bold]"
                    f" [dim]({conf})[/dim]"
                )
            console.print(
                Panel(
                    Markdown(result.get("raw", "")),
                    title=f"{name} — full analysis",
                    border_style="dim",
                )
            )

        status_cb = lambda msg: console.print(f"[dim]{msg}[/dim]")

        if batched:
            if compound_ctx:
                console.print(
                    f"[dim]Compound context ({', '.join(compound_ctx.sources)}); "
                    f"prefetching quotes per batch…[/dim]"
                )
            else:
                console.print("[dim]Prefetching live market data per batch…[/dim]")

            def on_batch_complete(batch_idx, n_batches, batch, panel_results, summary):
                console.print(
                    f"\n[bold cyan]Batch {batch_idx}/{n_batches} complete[/bold cyan] "
                    f"— {', '.join(batch)}"
                )
                _print_verdict_matrix(
                    panel_results, batch, f" (batch {batch_idx})"
                )
                console.print(
                    Panel(
                        Markdown(str(summary)),
                        title=f"Batch {batch_idx}/{n_batches} consensus",
                        border_style="dim",
                    )
                )

            panel_batches, batch_summaries, master, table_rows = (
                run_batched_consensus_analysis(
                    tickers,
                    agent.llm,
                    data_registry=data_registry,
                    agent=agent,
                    compound_ctx=compound_ctx,
                    status_callback=status_cb,
                    on_persona_complete=on_persona_complete,
                    on_batch_complete=on_batch_complete,
                    panel=panel,
                    ranking_instruction=ranking_instruction,
                )
            )

            master_table = Table(
                title=f"Master consensus — {len(tickers)} tickers",
                title_style="bold cyan",
                show_lines=True,
            )
            master_table.add_column("Ticker", style="white", no_wrap=True)
            master_table.add_column("Company", max_width=22)
            master_table.add_column("Price", justify="right")
            master_table.add_column("P/E", justify="right")
            master_table.add_column("Sector", max_width=14)
            master_table.add_column("Verdict", justify="center")
            master_table.add_column("Conf.", justify="center")
            master_table.add_column("Thesis", max_width=48)
            for row in table_rows:
                master_table.add_row(
                    row["ticker"],
                    row["company"],
                    row["price"],
                    row["pe"],
                    row["sector"],
                    row["verdict"],
                    row["confidence"],
                    row["thesis"],
                )
            console.print(master_table)
            console.print(
                Panel(
                    Markdown(str(master)),
                    title="Master consensus (all batches)",
                    border_style="cyan",
                )
            )
            if conversation is not None:
                memory_answer = format_batched_consensus_for_session_memory(
                    panel_batches,
                    batches,
                    batch_summaries,
                    str(master),
                )
                _record_llm_command_turn(
                    conversation,
                    manager,
                    user_query=prompt.strip(),
                    assistant_answer=memory_answer,
                    console=console,
                    followup_context={
                        "command": "/consensus",
                        "tickers": list(tickers),
                        "user_prompt": prompt.strip(),
                    },
                )
        else:
            prefetched_block = None
            if compound_ctx and compound_ctx.live_data_block:
                from .advanced.persona_market import format_persona_live_data_prefix

                prefetched_block = format_persona_live_data_prefix(
                    compound_ctx.live_data_block
                )
                console.print(
                    f"[dim]Using compound context ({', '.join(compound_ctx.sources)}) "
                    f"for market data…[/dim]"
                )
            else:
                console.print("[dim]Prefetching live market data for panel...[/dim]")
            panel_results, summary = run_consensus_analysis(
                tickers,
                agent.llm,
                data_registry=data_registry,
                agent=agent,
                live_data_block=prefetched_block,
                status_callback=status_cb,
                on_persona_complete=on_persona_complete,
                panel=panel,
                ranking_instruction=ranking_instruction,
            )
            _print_verdict_matrix(panel_results, tickers)
            console.print(
                Panel(
                    Markdown(str(summary)),
                    title="Consensus Summary",
                    border_style="cyan",
                )
            )
            if conversation is not None:
                memory_answer = format_consensus_for_session_memory(
                    panel_results,
                    tickers,
                    str(summary),
                )
                _record_llm_command_turn(
                    conversation,
                    manager,
                    user_query=prompt.strip(),
                    assistant_answer=memory_answer,
                    console=console,
                    followup_context={
                        "command": "/consensus",
                        "tickers": list(tickers),
                        "user_prompt": prompt.strip(),
                    },
                )
    except Exception as e:
        console.print(f"[red]Consensus error:[/red] {e}")
        logger = __import__("logging").getLogger(__name__)
        logger.exception("consensus command failed")

    return True
