"""Kleine instellingen die op deze computer bewaard blijven (bijv. de VirusTotal-sleutel)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _path() -> Path:
    if os.environ.get("CONVERTER_SETTINGS"):
        return Path(os.environ["CONVERTER_SETTINGS"])
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "AnythingConverter" / "settings.json"


def load() -> dict:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(p, 0o600)  # alleen voor deze gebruiker leesbaar
    except OSError:
        pass
