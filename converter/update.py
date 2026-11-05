"""Is there a newer release? One small request to GitHub, at most once a day; never blocks the app.

Turn it off with the environment variable ANYTHING_NO_UPDATE_CHECK=1.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request

API = "https://api.github.com/repos/WikiDave/The-Anything-Converter/releases/latest"
PAGE = "https://github.com/WikiDave/The-Anything-Converter/releases/latest"
_cache: dict = {}


def _tuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def newer(latest: str, current: str) -> bool:
    return _tuple(latest) > _tuple(current)


def latest(timeout: float = 4.0) -> dict | None:
    """{'version': '2.10.1', 'url': ...} or None (offline, turned off, rate limit)."""
    if os.environ.get("ANYTHING_NO_UPDATE_CHECK"):
        return None
    if _cache and time.time() - _cache.get("at", 0) < 86400:
        return _cache.get("data")
    data = None
    try:
        req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": "anything-converter-update-check"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.load(r)
        tag = str(j.get("tag_name") or "")
        if tag:
            data = {"version": tag.lstrip("v"), "url": j.get("html_url") or PAGE}
    except Exception:  # noqa: BLE001 - offline or blocked: just no notice
        data = None
    _cache.update(at=time.time(), data=data)
    return data


def how_to_update() -> str:
    import sys
    exe = os.path.realpath(sys.executable).lower()
    if "cellar" in exe or "homebrew" in exe or "linuxbrew" in exe:
        return "brew upgrade anything-converter"
    if "scoop" in exe:
        return "scoop update anything-converter"
    return PAGE
