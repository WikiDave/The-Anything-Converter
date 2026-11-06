"""Where the app's own files live (static/ web interface, VERSION), in every way it can be installed:

- from a git checkout or the desktop installers: next to app.py / the program
- from pip / pipx (any OS with Python: FreeBSD, OpenBSD, Termux, ...): inside the package, converter/_res
  (app.py, tui.py, static/, vendor/, VERSION are copied there when the wheel is built; see setup.py)
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

PKG = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def root() -> Path:
    """The folder that holds static/ (and usually VERSION)."""
    exe = Path(sys.executable).resolve().parent
    cands = [Path(os.environ["CONVERTER_BASE"])] if os.environ.get("CONVERTER_BASE") else []
    cands += [PKG.parent, PKG / "_res", PKG.parent.parent, exe, exe.parent / "Resources"]
    for c in cands:
        if (c / "static" / "index.html").is_file():
            return c
    return PKG.parent


def static_dir() -> Path:
    return root() / "static"


def version() -> str:
    exe = Path(sys.executable).resolve().parent
    for cand in (root() / "VERSION", PKG / "VERSION", exe / "VERSION", exe.parent / "Resources" / "VERSION"):
        try:
            return cand.read_text().strip()
        except OSError:
            pass
    try:
        from importlib.metadata import version as _v
        return _v("anything-converter")
    except Exception:  # noqa: BLE001
        return "0.0.0"
