"""Console commands for a pip / pipx install (anything-converter-tui, anything-converter).

app.py and tui.py ship inside the package (converter/_res) so they do not clash with other packages' modules.
"""
from __future__ import annotations

import sys

from .paths import root


def _res_on_path() -> None:
    r = str(root())
    if r not in sys.path:
        sys.path.insert(0, r)


def tui() -> int:
    """anything-converter-tui: the terminal version (and all commands: convert, drives, watch, serve, ...)."""
    _res_on_path()
    import tui as _tui  # noqa: PLC0415
    return _tui.run()


def web() -> int:
    """anything-converter: the app in your browser (same as 'anything-converter-tui serve')."""
    _res_on_path()
    import tui as _tui  # noqa: PLC0415
    return _tui.run(["serve", "--open", *sys.argv[1:]])


def desktop() -> int:
    """anything-converter-desktop: the window version (needs the 'desktop' extra: pywebview)."""
    _res_on_path()
    try:
        import webview  # noqa: F401, PLC0415
    except ImportError:
        print('The window version needs pywebview: pip install "anything-converter[desktop]".\n'
              "Without it, use 'anything-converter' (opens in your browser) or 'anything-converter-tui'.")
        return 1
    import runpy  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415
    launcher = Path(root()) / "desktop" / "launcher.py"
    sys.path.insert(0, str(launcher.parent))
    runpy.run_path(str(launcher), run_name="__main__")
    return 0
