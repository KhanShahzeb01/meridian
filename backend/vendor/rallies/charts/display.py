"""Show chart PNG in the terminal when the environment supports it."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def display_chart_in_terminal(path: Path, console) -> bool:
    """
    Try to render a PNG inline. Returns True if something was displayed.
    """
    path = Path(path)
    if not path.is_file():
        return False

    if shutil.which("chafa"):
        try:
            subprocess.run(
                ["chafa", "-s", "120x35", str(path)],
                check=False,
            )
            return True
        except OSError:
            pass

    term = (os.environ.get("TERM") or "").lower()
    if "kitty" in term and shutil.which("kitten"):
        try:
            subprocess.run(["kitten", "icat", str(path)], check=False)
            return True
        except OSError:
            pass

    if shutil.which("imgcat"):
        try:
            subprocess.run(["imgcat", str(path)], check=False)
            return True
        except OSError:
            pass

    try:
        from rich.console import Console
        from rich.panel import Panel

        # Rich can render images in supported terminals (e.g. iTerm2, some VTE).
        if getattr(Console(), "is_terminal", True):
            from rich.console import Group
            from rich.align import Align

            try:
                from rich.image import Image as RichImage
            except ImportError:
                RichImage = None  # type: ignore

            if RichImage is not None:
                img = RichImage.from_file(str(path))
                console.print(Panel(Align.center(img), border_style="dim"))
                return True
    except Exception:
        pass

    return False
