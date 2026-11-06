"""De terminalversie (tui.py) openen in een nieuw terminalvenster."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .paths import root as _root  # noqa: E402
ROOT = _root()


def tui_command() -> list[str]:
    if getattr(sys, "frozen", False):
        name = "anything-converter-tui.exe" if sys.platform == "win32" else "anything-converter-tui"
        exe = Path(sys.executable).resolve().parent / name
        if not exe.exists():
            raise RuntimeError(f"Terminal version not found: {exe}")
        return [str(exe)]
    return [sys.executable, str(ROOT / "tui.py")]


# Linux-terminals en hoe je ze een programma laat starten
LINUX_TERMINALS = [
    ("x-terminal-emulator", ["-e"]), ("gnome-terminal", ["--"]), ("ptyxis", ["--"]), ("kgx", ["--"]),
    ("konsole", ["-e"]), ("xfce4-terminal", ["-x"]), ("mate-terminal", ["-x"]), ("tilix", ["-e"]),
    ("kitty", []), ("alacritty", ["-e"]), ("wezterm", ["start", "--"]), ("foot", []), ("xterm", ["-e"]),
]


def open_tui() -> None:
    cmd = tui_command()
    home = str(Path.home())
    if sys.platform == "win32":
        subprocess.Popen(cmd, cwd=home, creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)
        return
    if sys.platform == "darwin":
        # Terminal.app opent een .command-bestand als script in een nieuw venster
        script = Path(tempfile.gettempdir()) / "anything-converter-tui.command"
        script.write_text(f"#!/bin/sh\ncd {shlex.quote(home)}\nexec {shlex.join(cmd)}\n")
        script.chmod(0o755)
        subprocess.Popen(["open", "-a", "Terminal", str(script)])
        return
    env = dict(os.environ)
    if "UTF-8" not in (env.get("LC_ALL") or env.get("LC_CTYPE") or env.get("LANG") or "").upper().replace("UTF8", "UTF-8"):
        env["LC_ALL"] = "C.UTF-8"  # kaders en blokjes goed tonen
    for term, args in LINUX_TERMINALS:
        path = shutil.which(term)
        if path:
            subprocess.Popen([path, *args, *cmd], cwd=home, env=env, start_new_session=True)
            return
    raise RuntimeError("No terminal program found. Run in a terminal: " + shlex.join(cmd))
