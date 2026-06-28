"""Meridian engine — vendored command router (standalone, not linked to rallies-cli install)."""

from __future__ import annotations

import re
import traceback
from io import StringIO
from typing import Any, Optional

from rich.console import Console

from services.bootstrap import bootstrap, meridian_home

bootstrap()

from rallies.manager import Manager  # noqa: E402
from rallies.helpers import (  # noqa: E402
    load_config,
    save_config,
    show_help,
    get_api_key,
)
from rallies.advanced.personas import list_personas_by_category  # noqa: E402
from rallies.cli_completions import SLASH_COMMANDS  # noqa: E402

from services.command_format import format_command_markdown
from services.fast_chat import run_fast_chat
from services.fast_memo import run_fast_memo
from services.fast_router import (
    format_personas_markdown,
    is_data_fast_command,
    is_fast_ask,
    is_heavy_command,
    is_instant_command,
    run_slow_command,
    try_data_fast,
    try_fast_ask_path,
    try_instant,
)
from services.rich_parser import extract_sections, primary_content
from rallies.llm import LLMError

BOX_DRAWING = re.compile(r"[\u2500-\u257F]")
RICH_TAGS = re.compile(r"\[/?[a-z_]+\]", re.IGNORECASE)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
MULTI_NEWLINE = re.compile(r"\n{3,}")

CATEGORY_COLORS = {
    "Value Investors": "#F59E0B",
    "Growth Investors": "#10B981",
    "Macro / Global": "#6366F1",
    "Quantitative": "#06B6D4",
    "Hedge Fund Managers": "#EF4444",
    "Economic": "#8B5CF6",
    "Tech / Innovation": "#EC4899",
}

COMMANDS_STRUCTURE: dict[str, Any] = {
    "Screener": {
        "commands": [
            {"cmd": "/screen [criteria]", "desc": "Multi-agent stock screener"},
            {"cmd": "/screen sector=tech style=value", "desc": "Structured: sector, style, min_mcap, max_pe"},
        ],
    },
    "Compound": {
        "commands": [
            {"cmd": "/compound_help", "desc": "Guide for chaining commands on one line"},
        ],
    },
    "Research": {
        "commands": [
            {"cmd": "/rules", "desc": "Show research rules"},
            {"cmd": "/soul", "desc": "Show tone overlay"},
            {"cmd": "/fetch URL", "desc": "Fetch URL → markdown"},
            {"cmd": "/bundle TICKER", "desc": "Parallel quote + SEC diagnostic"},
            {"cmd": "/skill [NAME]", "desc": "List or load SKILL.md workflows"},
            {"cmd": "/memo TICKER long|short", "desc": "Investment memo → HTML"},
            {"cmd": "/filing TICKER [section]", "desc": "SEC filing section"},
            {"cmd": "/research QUERY", "desc": "Deep-dive research with tools"},
            {"cmd": "/research-log", "desc": "Last scratchpad log"},
        ],
    },
    "Personas": {
        "commands": [
            {"cmd": "/personas", "desc": "List all 36 AI agent personas"},
            {"cmd": "/ask PERSONA Q", "desc": "Ask a persona"},
            {"cmd": "/debate A vs B Q", "desc": "Debate between personas"},
            {"cmd": "/consensus $TICKER", "desc": "7-category expert panel + vote"},
        ],
    },
    "Quant": {
        "commands": [
            {"cmd": "/dcf TICKER [g] [r]", "desc": "DCF valuation"},
            {"cmd": "/optimize [risk 1-10] [TICKERS]", "desc": "Rebalance portfolio"},
            {"cmd": "/options TICKER", "desc": "Options chain + Black-Scholes"},
            {"cmd": "/analysis TICKER", "desc": "Quant stats (Sharpe, Sortino)"},
            {"cmd": "/chart TICKER [5y]", "desc": "Valuation dashboard"},
        ],
    },
    "Data": {
        "commands": [
            {"cmd": "/quote TICKER", "desc": "Real-time price, P/E, market cap"},
            {"cmd": "/financials TICKER", "desc": "Multi-year income statement"},
            {"cmd": "/sec TICKER [FORM]", "desc": "SEC filings"},
            {"cmd": "/earnings TICKER", "desc": "Earnings dates & surprises"},
            {"cmd": "/earnings", "desc": "Upcoming earnings calendar"},
            {"cmd": "/news TICKER", "desc": "Latest headlines"},
            {"cmd": "/peers TICKER", "desc": "Peer comparison"},
            {"cmd": "/index NAME", "desc": "SP500, NASDAQ, DJI"},
            {"cmd": "/vix", "desc": "Volatility Index"},
            {"cmd": "/searchsec QUERY", "desc": "SEC full-text search"},
        ],
    },
    "Analysis": {
        "commands": [
            {"cmd": "/insider TICKER", "desc": "Insider trades (Form 4)"},
            {"cmd": "/holdings TICKER", "desc": "Institutional holders"},
            {"cmd": "/macro", "desc": "Economic dashboard"},
            {"cmd": "/hedgefund", "desc": "Hedge fund positioning"},
            {"cmd": "/sector NAME", "desc": "Sector overview"},
        ],
    },
    "Portfolio": {
        "commands": [
            {"cmd": "/tickers list [PREFIX]", "desc": "Browse ticker catalog"},
            {"cmd": "/watchlist", "desc": "Default watchlist"},
            {"cmd": "/watchlist add TICKER", "desc": "Add to watchlist"},
            {"cmd": "/watchlist watchlists", "desc": "List watchlist names"},
            {"cmd": "/portfolio", "desc": "Default portfolio"},
            {"cmd": "/portfolio add TICKER QTY PRICE", "desc": "Add position"},
            {"cmd": "/portfolio portfolios", "desc": "List portfolio names"},
            {"cmd": "/alert TICKER %", "desc": "Price alert"},
            {"cmd": "/alerts", "desc": "Check alerts"},
        ],
    },
    "System": {
        "commands": [
            {"cmd": "/key API_KEY", "desc": "Set OpenRouter API key"},
            {"cmd": "/history", "desc": "Saved sessions"},
            {"cmd": "/export [PATH]", "desc": "Export to markdown"},
            {"cmd": "/resume PATH", "desc": "Resume from export"},
            {"cmd": "/clear", "desc": "Clear conversation"},
            {"cmd": "/compact", "desc": "Compact conversation"},
            {"cmd": "/example [topic]", "desc": "Example prompts"},
            {"cmd": "/help", "desc": "Full command menu"},
        ],
    },
}


class CaptureConsole(Console):
    def __init__(self):
        self.buffer = StringIO()
        self._response_markdown: list[str] = []
        super().__init__(file=self.buffer, force_terminal=False, width=120)

    def print(self, *args, **kwargs):
        from rich.markdown import Markdown
        from rich.panel import Panel

        for arg in args:
            if isinstance(arg, Panel):
                title = str(arg.title or "").strip()
                renderable = arg.renderable
                if title == "Response" and isinstance(renderable, Markdown):
                    markup = getattr(renderable, "markup", None)
                    if markup and str(markup).strip():
                        self._response_markdown.append(str(markup).strip())
        return super().print(*args, **kwargs)

    def consume_response_markdown(self) -> Optional[str]:
        if not self._response_markdown:
            return None
        return self._response_markdown.pop(0)

    def reset_capture(self) -> None:
        self._response_markdown.clear()

    def get_output(self) -> str:
        val = self.buffer.getvalue()
        self.buffer.truncate(0)
        self.buffer.seek(0)
        return val


def _build_result(
    result_type: str,
    raw_output: str,
    *,
    query: str = "",
    is_command: bool = False,
    persona: Optional[str] = None,
    answer_markdown: Optional[str] = None,
) -> dict[str, Any]:
    if answer_markdown and answer_markdown.strip():
        md = answer_markdown.strip()
        sections = {
            "planning": None,
            "thinking": None,
            "response": md,
            "panels": None,
            "extra": None,
        }
        content = md
    else:
        sections = extract_sections(raw_output)
        captured = _console.consume_response_markdown()
        if captured:
            sections["response"] = captured
        content = primary_content(sections, raw_output)
        if sections.get("response"):
            content = sections["response"]

    payload: dict[str, Any] = {
        "type": result_type,
        "content": content or "No response from model. Check API credits or try again.",
        "sections": sections,
        "query": query,
    }
    if is_command:
        payload["is_command"] = True
    if persona:
        payload["persona"] = persona
    return payload


def clean_rich_output(text: str) -> str:
    if not text:
        return text
    text = ANSI_ESCAPE.sub("", text)
    text = RICH_TAGS.sub("", text)
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped and BOX_DRAWING.sub("", stripped).strip() in ("", "─", "━", "═"):
            continue
        if not stripped:
            cleaned.append("")
            continue
        line = line.replace("\u2502", "|").replace("\u2503", "|")
        cleaned.append(line.rstrip())
    text = "\n".join(cleaned)
    return MULTI_NEWLINE.sub("\n\n", text).strip()


_manager: Manager | None = None
_conversations: dict[str, list] = {}
_console = CaptureConsole()


def init_manager() -> Manager | None:
    global _manager
    if _manager is not None:
        return _manager
    bootstrap()
    try:
        _manager = Manager()
        return _manager
    except ValueError as e:
        if "API key" in str(e):
            return None
        raise


def get_personas_grouped() -> dict[str, list[dict]]:
    grouped = list_personas_by_category()
    result = {}
    for cat, personas in grouped.items():
        result[cat] = [
            {
                "id": p["key"],
                "name": p["name"],
                "short": p.get("short", p["key"]),
                "title": p.get("style", ""),
                "category": cat,
                "quote": p.get("quote", ""),
                "avatar": "".join(w[0] for w in p["name"].split()[:2]).upper(),
                "color": CATEGORY_COLORS.get(cat, "#94A3B8"),
            }
            for p in personas
        ]
    return result


def get_all_personas_flat() -> list[dict]:
    return [p for group in get_personas_grouped().values() for p in group]


def _get_conversation(session_id: str) -> list:
    if session_id not in _conversations:
        _conversations[session_id] = []
    return _conversations[session_id]


def apply_request_api_key(api_key: Optional[str]) -> None:
    """Use client-provided key for this request only — never written to disk."""
    global _manager
    if not api_key or not str(api_key).strip():
        return
    import os

    key = str(api_key).strip()
    os.environ["OPENROUTER_API_KEY"] = key
    if _manager and hasattr(_manager, "agent") and hasattr(_manager.agent, "set_api_key"):
        _manager.agent.set_api_key(key)
        return
    _manager = None
    init_manager()


def process_prompt(
    prompt: str,
    session_id: str = "default",
    persona_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Route prompt: slash commands always; free-text uses persona only if explicitly set."""
    apply_request_api_key(api_key)
    prompt = prompt.strip()
    if not prompt:
        return {"type": "empty", "content": ""}

    manager = init_manager()
    conversation = _get_conversation(session_id)

    # Persona only when side panel selection is active — never auto-wrap slash commands
    routed = prompt
    if not prompt.startswith("/") and persona_id and persona_id.strip():
        routed = f"/ask {persona_id.strip()} {prompt}"

    try:
        _console.reset_capture()
        routed_l = routed.strip().lower()
        cmd = routed.split()[0].lower() if routed.startswith("/") else "chat"
        cmd_type = _command_type(cmd)

        # Instant — no LLM, no rallies
        if is_instant_command(routed):
            instant_md = try_instant(
                routed,
                conversation,
                _console,
                personas_formatter=format_personas_markdown,
            )
            if instant_md is not None:
                return _build_result(
                    cmd_type,
                    "",
                    query=prompt,
                    is_command=True,
                    answer_markdown=instant_md,
                )

        # Fast /memo — skip rallies 5-step pipeline
        if routed_l.startswith("/memo") and "--full" not in routed_l.split():
            if not manager:
                return {
                    "type": "error",
                    "content": "Set your OpenRouter API key with `/key YOUR_KEY` to enable memo.",
                    "sections": {"response": "API key required."},
                    "query": prompt,
                }
            try:
                memo_md = run_fast_memo(routed, manager, _console)
                return _build_result(
                    "memo",
                    _console.get_output(),
                    query=prompt,
                    is_command=True,
                    answer_markdown=memo_md,
                )
            except Exception as exc:
                if isinstance(exc, LLMError):
                    err = exc.user_message(
                        model=getattr(manager.agent.llm, "last_model", None),
                        technical=False,
                    )
                else:
                    err = f"Memo failed: {exc}"
                return {
                    "type": "error",
                    "content": err,
                    "sections": {"response": err},
                    "query": prompt,
                }

        # Data-only commands — skip rallies entirely (no double fetch)
        if is_data_fast_command(routed):
            formatted = try_data_fast(routed, manager, cmd_type)
            if formatted:
                return _build_result(
                    cmd_type,
                    "",
                    query=prompt,
                    is_command=True,
                    answer_markdown=formatted,
                )

        # /ask and persona-wrapped chat — single LLM call
        if is_fast_ask(routed):
            if not manager:
                return {
                    "type": "error",
                    "content": "Set your OpenRouter API key with `/key YOUR_KEY` to enable chat.",
                    "sections": {"response": "API key required."},
                    "query": prompt,
                }
            try:
                answer = try_fast_ask_path(routed, conversation, manager)
                return _build_result(
                    "analysis",
                    "",
                    query=prompt,
                    persona=routed.split()[1] if routed.startswith("/ask") else None,
                    answer_markdown=answer,
                )
            except LLMError as exc:
                err = exc.user_message(
                    model=getattr(manager.agent.llm, "last_model", None),
                    technical=False,
                )
                return {
                    "type": "error",
                    "content": err,
                    "sections": {"response": err},
                    "query": prompt,
                }

        # Heavy / stateful commands — full rallies pipeline
        if routed.startswith("/") and (is_heavy_command(routed) or not is_data_fast_command(routed)):
            if manager and run_slow_command(routed, conversation, manager, _console):
                raw = _console.get_output()
                formatted = format_command_markdown(cmd_type, routed, manager)
                return _build_result(
                    cmd_type,
                    raw,
                    query=prompt,
                    is_command=True,
                    answer_markdown=formatted if formatted and not is_heavy_command(routed) else None,
                )
            if routed.startswith("/"):
                raw = _console.get_output()
                if raw.strip():
                    return _build_result("command", raw, query=prompt, is_command=True)

        if not manager:
            return {
                "type": "error",
                "content": "Set your OpenRouter API key with `/key YOUR_KEY` to enable chat.",
                "sections": {"response": "Set your OpenRouter API key with `/key YOUR_KEY` to enable chat."},
                "query": prompt,
            }

        # General conversation — fast single-shot LLM
        try:
            answer = run_fast_chat(prompt, conversation, manager)
            return _build_result("chat", "", query=prompt, answer_markdown=answer)
        except LLMError as exc:
            model = getattr(manager.agent.llm, "last_model", None)
            err = exc.user_message(model=model, technical=False)
            return {
                "type": "error",
                "content": err,
                "sections": {"response": err},
                "query": prompt,
            }

    except LLMError as exc:
        model = getattr(manager.agent.llm, "last_model", None) if manager else None
        err = exc.user_message(model=model, technical=False)
        return {
            "type": "error",
            "content": err,
            "sections": {"response": err},
            "query": prompt,
        }

    except Exception as e:
        traceback.print_exc()
        raw = _console.get_output()
        err = f"Error: {e}"
        if raw.strip():
            err = f"{err}\n\n{clean_rich_output(raw)}"
        return {
            "type": "error",
            "content": err.strip(),
            "sections": extract_sections(raw) if raw.strip() else {"response": err},
            "query": prompt,
        }


def _command_type(cmd: str) -> str:
    mapping = {
        "/help": "help",
        "/quote": "quote",
        "/financials": "financials",
        "/news": "news",
        "/dcf": "dcf",
        "/sec": "filings",
        "/filing": "filings",
        "/consensus": "consensus",
        "/ask": "analysis",
        "/debate": "debate",
        "/personas": "personas",
        "/screen": "screener",
        "/watchlist": "watchlist",
        "/portfolio": "portfolio",
        "/clear": "clear",
        "/macro": "macro",
        "/vix": "vix",
        "/research": "research",
        "/memo": "memo",
    }
    return mapping.get(cmd, "command")


def get_help_text() -> str:
    show_help(_console)
    raw = _console.get_output()
    sections = extract_sections(raw)
    return primary_content(sections, raw)


def set_api_key(key: str) -> bool:
    cfg = load_config()
    cfg["openrouter_api_key"] = key
    cfg["api_key"] = key
    import os

    os.environ["OPENROUTER_API_KEY"] = key
    cfg_path = meridian_home() / "config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if save_config(cfg):
        global _manager
        if _manager and hasattr(_manager.agent, "set_api_key"):
            _manager.agent.set_api_key(key)
        else:
            _manager = None
            init_manager()
        return True
    return False


def get_status() -> dict:
    return {
        "initialized": _manager is not None,
        "has_api_key": False,
        "client_api_key": True,
        "engine": "meridian-vendor",
        "data_dir": str(meridian_home()),
    }


def clear_session(session_id: str) -> None:
    _conversations[session_id] = []


def get_slash_commands() -> list[str]:
    return list(SLASH_COMMANDS)
