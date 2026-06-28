"""Meridian bootstrap — isolated data paths and config (separate from rallies-cli)."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = BACKEND_ROOT / "vendor"
MERIDIAN_HOME = Path(os.environ.get("MERIDIAN_DATA_DIR", Path.home() / ".meridian"))
_PROVIDER_CONFIG = BACKEND_ROOT / "config" / "provider.yaml"

_bootstrapped = False


def meridian_home() -> Path:
    MERIDIAN_HOME.mkdir(parents=True, exist_ok=True)
    return MERIDIAN_HOME


def _seed_config() -> None:
    cfg_path = meridian_home() / "config.json"
    if cfg_path.exists():
        return
    rallies_cfg = Path.home() / ".rallies" / "config.json"
    if rallies_cfg.exists():
        shutil.copy(rallies_cfg, cfg_path)
        return
    cfg_path.write_text(json.dumps({}, indent=2))


def _seed_env_file() -> None:
    env_path = BACKEND_ROOT / ".env"
    lines: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                lines[k.strip()] = v.strip()

    cfg = {}
    cfg_path = meridian_home() / "config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text())
        except json.JSONDecodeError:
            pass

    or_key = (
        cfg.get("openrouter_api_key")
        or cfg.get("api_key")
        or os.environ.get("OPENROUTER_API_KEY", "")
    )
    if or_key:
        lines["OPENROUTER_API_KEY"] = or_key
        os.environ["OPENROUTER_API_KEY"] = or_key

    for key in ("FRED_API_KEY", "FINNHUB_API_KEY", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"):
        val = os.environ.get(key) or lines.get(key)
        if val:
            lines[key] = val
            os.environ[key] = val

    if _PROVIDER_CONFIG.exists():
        lines.setdefault(
            "MERIDIAN_PROVIDER_CONFIG",
            str(_PROVIDER_CONFIG),
        )
        os.environ["RALLIES_PROVIDER_CONFIG"] = str(_PROVIDER_CONFIG)

    lines.setdefault("MERIDIAN_DATA_DIR", str(meridian_home()))
    lines.setdefault("CORS_ORIGINS", "http://localhost:3000")

    env_path.write_text("\n".join(f"{k}={v}" for k, v in lines.items()) + "\n")


def _patch_vendor_paths() -> None:
    """Redirect vendored engine storage paths to ~/.meridian."""
    home = meridian_home()

    from rallies.research import paths as research_paths

    research_paths.rallies_data_dir = lambda: home  # type: ignore[method-assign]

    from rallies import storage as storage_mod

    _orig_storage_init = storage_mod.Storage.__init__

    def _storage_init(self, db_path=None):
        _orig_storage_init(self, db_path or (home / "meridian.db"))

    storage_mod.Storage.__init__ = _storage_init  # type: ignore[method-assign]

    from rallies import ticker_library as ticker_lib

    def _user_tickers_path():
        return home / ticker_lib.USER_TICKERS_FILENAME

    ticker_lib.user_tickers_path = _user_tickers_path  # type: ignore[method-assign]

    from rallies import helpers as helpers_mod

    def _get_config_dir():
        home.mkdir(parents=True, exist_ok=True)
        return home

    helpers_mod.get_config_dir = _get_config_dir  # type: ignore[method-assign]
    helpers_mod.get_config_file = lambda: home / "config.json"  # type: ignore[method-assign]


def bootstrap() -> None:
    global _bootstrapped
    if _bootstrapped:
        return

    meridian_home()
    _seed_config()
    _seed_env_file()

    os.environ["MERIDIAN_DATA_DIR"] = str(meridian_home())
    os.environ["RALLIES_DATA_DIR"] = str(meridian_home())
    os.environ.setdefault("RALLIES_GRAPH_PLANNER", "0")
    os.environ.setdefault("RALLIES_GRAPH_RESEARCH", "0")
    os.environ.setdefault("RALLIES_GRAPH_CHECKPOINTS", "0")

    vendor_str = str(VENDOR_ROOT)
    # Prepend vendor so we never import the external rallies-cli install
    sys.path = [p for p in sys.path if "rallies-cli" not in p.replace("\\", "/")]
    if vendor_str not in sys.path:
        sys.path.insert(0, vendor_str)

    _patch_vendor_paths()
    from services.market_data import patch_data_sources

    patch_data_sources()
    _bootstrapped = True
