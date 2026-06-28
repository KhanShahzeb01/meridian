import atexit
import sys
import os
import shutil
import textwrap

# DECSET 1004 off — stops ESC [ I / ESC [ O on window focus (minimize/click).
_FOCUS_REPORTING_OFF = "\033[?1004l"
from rich.panel import Panel
from rich.text import Text
from rallies.manager import Manager
from rallies import console
from rallies.helpers import log_session_ended
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.styles import Style
except ImportError:  # graceful fallback to input()
    PromptSession = None
    Completer = object
    Completion = None
    Style = None

from rallies.cli_completions import (
    iter_slash_command_completions,
    iter_ticker_completion_rows,
    ticker_completion_fragment,
)


class RalliesCompleter(Completer):
    """$TICKER anywhere in the line; slash commands on the first token only."""

    def get_completions(self, document, complete_event):
        if Completion is None:
            return
        text = document.text_before_cursor

        fragment = ticker_completion_fragment(text)
        if fragment is not None:
            for row in iter_ticker_completion_rows(text, limit=30):
                sym = row["symbol"]
                name = (row.get("name") or "").strip()
                display = f"{sym} — {name[:48]}" if name else sym
                yield Completion(
                    sym,
                    start_position=-len(fragment),
                    display=display,
                    display_meta=row.get("exchange", ""),
                )
            return

        stripped = text.lstrip()
        for cmd in iter_slash_command_completions(text):
            yield Completion(cmd, start_position=-len(stripped))


PROMPT_LABEL = "› "
PROMPT_STYLE = (
    Style.from_dict(
        {
            # Keep the prompt dark/transparent so no bright bands are painted.
            "prompt": "bold ansicyan",
            "": "",
            "bottom-toolbar": "bg:#1a1a1a #666666",
        }
    )
    if Style
    else None
)
FALLBACK_PROMPT_BG = "\033[48;5;235m\033[38;5;45m"
FALLBACK_PROMPT_RESET = "\033[0m"


def _bg_fill_line_ansi():
    width = shutil.get_terminal_size(fallback=(80, 24)).columns
    return f"{FALLBACK_PROMPT_BG}{' ' * max(1, width)}{FALLBACK_PROMPT_RESET}\n"


def _count_prompt_visual_lines(user_input_text: str) -> int:
    width = shutil.get_terminal_size(fallback=(80, 24)).columns
    first_line_width = max(1, width - len(PROMPT_LABEL))
    continuation_width = max(1, width)
    lines = user_input_text.splitlines() or [user_input_text]
    total = 0
    for i, line in enumerate(lines):
        line_width = first_line_width if i == 0 else continuation_width
        wrapped = textwrap.wrap(line, width=line_width) or [""]
        total += len(wrapped)
    return max(1, total)


def _is_conversation_meta_command(text: str) -> bool:
    """Commands that manage the thread without adding a user turn."""
    p = text.strip().lower()
    return p.startswith("/export") or p.startswith("/resume")


def _disable_terminal_focus_reporting() -> None:
    """Prevent focus-in/out CSI sequences from echoing as ^[[I / ^[[O."""
    if sys.stdout.isatty():
        sys.stdout.write(_FOCUS_REPORTING_OFF)
        sys.stdout.flush()


def _clear_echoed_prompt_input(user_input_text: str):
    # prompt_toolkit keeps the entered query visible on the prompt line(s).
    # Remove those visual lines so the query appears only in the blue Query panel.
    visual_lines = _count_prompt_visual_lines(user_input_text)
    for _ in range(visual_lines):
        sys.stdout.write("\x1b[1A\x1b[2K")
    sys.stdout.flush()


def get_env_file_path():
    return os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        ),
        ".env",
    )

def display_application_banner():
    banner_text = """
██╗    ██████╗ █████╗ ██╗     ██╗     ██╗███████╗███████╗
  ██╗  ██╔══██╗██╔══██╗██║     ██║     ██║██╔════╝██╔════╝
    ██ ╗█████╔╝███████║██║     ██║     ██║█████╗  ███████╗
  ██╔╝ ██╔══██╗██╔══██║██║     ██║     ██║██╔══╝  ╚════██║
██╔╝   ██║  ██║██║  ██║███████╗███████╗██║███████╗███████║
╚╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚══════╝╚══════╝
"""
    
    # Create gradient effect similar to Gemini CLI
    lines = banner_text.strip().split('\n')
    gradient_colors = ['bright_blue', 'blue', 'cyan', 'bright_cyan', 'magenta', 'bright_magenta']
    
    styled_lines = []
    for i, line in enumerate(lines):
        color = gradient_colors[i % len(gradient_colors)]
        styled_lines.append(Text(line, style=f"bold {color}"))
    
    # Combine all lines
    full_banner = Text()
    full_banner.append("\n\n")
    for line in styled_lines:
        full_banner.append(line)
        full_banner.append('\n')
    
    # Add subtitle with gradient
    subtitle = Text("AI powered investment research, backed by real-time data", style="bold bright_magenta")
    full_banner.append('\n')
    full_banner.append(subtitle)
    
    # Print banner without border, left-aligned like Gemini CLI
    console.print(full_banner)

def interactive_shell():
    _disable_terminal_focus_reporting()
    atexit.register(_disable_terminal_focus_reporting)

    display_application_banner()
    
    # Tips section for user guidance
    console.print("\n[dim white]Tips for getting started:[/dim white]")
    console.print("[white]1. Use $ before tickers in questions (e.g. compare $AAPL vs $MSFT).[/white]")
    console.print("[white]2. Type $ to autocomplete tickers (works in /commands and free text).[/white]")
    console.print("[white]3. Type /help for commands; /tickers to manage your symbol list.[/white]\n")
    
    # Use free agent by default
    selected_agent = Manager()
    session = (
        PromptSession(
            completer=RalliesCompleter(),
            complete_while_typing=True,
            style=PROMPT_STYLE,
            bottom_toolbar=[("class:bottom-toolbar", " ")],
        )
        if PromptSession
        else None
    )
    
    print("\nType your queries below. Press Ctrl+C to exit.\n")
    messages = []
    try:
        while True:
            _disable_terminal_focus_reporting()
            if session:
                user_input_text = session.prompt(
                    [("class:prompt", PROMPT_LABEL)]
                )
            else:
                # Display prompt + input area with a background band in fallback mode.
                sys.stdout.write(_bg_fill_line_ansi())
                sys.stdout.write(f"{FALLBACK_PROMPT_BG}{PROMPT_LABEL}")
                sys.stdout.flush()
                user_input_text = input()
                sys.stdout.write(FALLBACK_PROMPT_RESET)
                sys.stdout.write("\n")
                sys.stdout.write(_bg_fill_line_ansi())
                sys.stdout.flush()
            
            if user_input_text.strip():
                if session:
                    _clear_echoed_prompt_input(user_input_text)
                console.print(
                    Panel(
                        f"[bold]{user_input_text.strip()}[/bold]",
                        title="Query",
                        border_style="blue",
                    )
                )
                if not _is_conversation_meta_command(user_input_text):
                    messages.append({"role": "user", "content": user_input_text})
                try:
                    selected_agent.process_prompt(user_input_text, messages)
                finally:
                    # Rich Live spinners do not read stdin; refocus events would echo.
                    _disable_terminal_focus_reporting()
            else:
                console.print("[yellow]Please enter a query.[/yellow]\n")
                
    except KeyboardInterrupt:
        _disable_terminal_focus_reporting()
        try:
            log_session_ended(
                selected_agent.history_session,
                "user_interrupt",
                "Exiting the CLI (Ctrl+C).",
                phase="cli_exit",
            )
        except Exception:
            pass
        print("\n\nGoodbye!")
        sys.exit(0)

def main():
    # Load .env file for API keys
    env_path = get_env_file_path()
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                    val = val[1:-1]
                if key.startswith("export "):
                    key = key[7:]
                if not os.environ.get(key):
                    os.environ[key] = val

    interactive_shell()

if __name__ == '__main__':
    main()
