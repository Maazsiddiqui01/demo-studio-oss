"""Paths, settings and timing defaults shared by every stage.

The workspace is DEMO_STUDIO_HOME, or the current folder: renders go to <workspace>/out/ and
`studio login` looks for storyboards there. Settings (publishing) come from
<workspace>/demo-studio.yaml, then from the user config file (see user_config_path()).
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

PKG = Path(__file__).resolve().parent
TEMPLATES = PKG / "templates"


def home() -> Path:
    return Path(os.environ.get("DEMO_STUDIO_HOME") or Path.cwd()).resolve()


def out_root() -> Path:
    return Path(os.environ.get("DEMO_STUDIO_OUT") or home() / "out")


def _platform_dir(kind: str) -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "demo-studio" / kind
    if sys.platform == "darwin":
        sub = {"cache": "Library/Caches", "data": "Library/Application Support"}[kind]
        return Path.home() / sub / "demo-studio"
    env = {"cache": "XDG_CACHE_HOME", "data": "XDG_DATA_HOME"}[kind]
    default = {"cache": ".cache", "data": ".local/share"}[kind]
    return Path(os.environ.get(env) or Path.home() / default) / "demo-studio"


def cache_dir() -> Path:
    """Voice models and the narration cache. Safe to delete; it refills on the next render."""
    return Path(os.environ.get("DEMO_STUDIO_CACHE") or _platform_dir("cache"))


def auth_dir() -> Path:
    """Saved sign-in sessions live outside every repo and are never uploaded."""
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "demo-studio" / "auth"
    return _platform_dir("data") / "auth"


def user_config_path() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home()) / "demo-studio" / "config.yaml"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "demo-studio" / "config.yaml"


@lru_cache(maxsize=None)
def settings() -> dict:
    """Merged settings: the workspace's demo-studio.yaml wins over the user config file.
    Each section remembers the folder its file was in (`_dir`), for relative paths."""
    import yaml
    merged: dict = {}
    for p in (user_config_path(), home() / "demo-studio.yaml"):
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            for section, values in data.items():
                if isinstance(values, dict):
                    merged.setdefault(section, {}).update(values)
                    merged[section]["_dir"] = str(p.parent)
                else:
                    merged[section] = values
    return merged


def out_dir_for(sb) -> Path:
    """Handover renders go under out/clients/<client>/, public ones under out/<name>/."""
    if sb.mode == "handover":
        return out_root() / "clients" / sb.client / sb.name
    return out_root() / sb.name


# Timing, in seconds
LEAD_IN = 0.35          # gap between a step starting and its narration starting
TAIL = 0.7              # gap after the narration before the next step starts
CURSOR_MOVE = 0.75      # fake cursor travel time before a click
ZOOM_MS = 750           # zoom in or out
SLIDE_MIN = 3.5         # minimum time a title slide is on screen
FPS = 30
