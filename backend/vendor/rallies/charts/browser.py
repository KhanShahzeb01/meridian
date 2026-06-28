"""Open Plotly HTML in the system browser without Python's firefox default."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

# Prefer Chrome/Chromium; avoid webbrowser module (often picks firefox on Linux).
_CHROME_NAMES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
)


def open_html_file(path: Path) -> bool:
    """
    Open a local HTML file. Returns True if a launcher was started.

    Set RALLIES_BROWSER to a binary name or full path (e.g. google-chrome).
    """
    path = Path(path).resolve()
    if not path.is_file():
        return False

    uri = path.as_uri()
    commands: list[list[str]] = []

    custom = (os.environ.get("RALLIES_BROWSER") or "").strip()
    if custom:
        commands.append([custom, uri])

    for name in _CHROME_NAMES:
        exe = shutil.which(name)
        if exe:
            commands.append([exe, uri])

    xdg = shutil.which("xdg-open")
    if xdg:
        commands.append([xdg, uri])

    for cmd in commands:
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except OSError:
            continue

    return False
