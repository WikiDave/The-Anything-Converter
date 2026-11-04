"""Anything Converter - desktop-app.

Start de converter op de achtergrond en opent hem in je standaardbrowser.
Draait hij al, dan wordt alleen de browser geopend. Afsluiten gaat met
[ AFSLUITEN ] bovenaan de pagina.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

PREFERRED_PORT = 8737
HOST = "127.0.0.1"


def app_dir() -> Path:
    """Map met static/ en bin/: naast het programma (bevroren) of de projectmap (ontwikkeling)."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        # macOS .app: Contents/MacOS/<exe>; bestanden staan ook daar (cx_Freeze) of in Resources
        for cand in (exe.parent, exe.parent.parent / "Resources"):
            if (cand / "static").is_dir():
                return cand
        return exe.parent
    return Path(__file__).resolve().parent.parent


def log_file() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Logs"
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    root = root / "AnythingConverter"
    root.mkdir(parents=True, exist_ok=True)
    return root / "anything-converter.log"


def prepare_environment(base: Path) -> None:
    # Meegeleverde programma's (ffmpeg, ffprobe, deno) gaan voor.
    paths = [str(base / "bin")] if (base / "bin").is_dir() else []
    paths.append(os.environ.get("PATH", ""))
    # Apps die vanuit Finder/Start worden gestart krijgen een kaal PATH; voeg bekende plekken toe
    # zodat een los geïnstalleerd LibreOffice/pandoc/Ghostscript ook gevonden wordt.
    for extra in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin",
                  "/Applications/LibreOffice.app/Contents/MacOS",
                  r"C:\Program Files\LibreOffice\program", r"C:\Program Files\Pandoc",
                  r"C:\Program Files\gs\bin"):
        if os.path.isdir(extra):
            paths.append(extra)
    os.environ["PATH"] = os.pathsep.join(p for p in paths if p)
    os.environ["CONVERTER_BASE"] = str(base)
    os.environ["CONVERTER_DESKTOP"] = "1"
    os.environ.setdefault("CONVERTER_WORKDIR", str(Path(tempfile.gettempdir()) / "anything-converter"))


def already_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/ping", timeout=1.5) as r:
            return json.load(r).get("app") == "anything-converter"
    except Exception:
        return False


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, port))
            return True
        except OSError:
            return False


def pick_port() -> int:
    if port_free(PREFERRED_PORT):
        return PREFERRED_PORT
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def main() -> None:
    base = app_dir()
    # Een GUI-app heeft geen console: schrijf uitvoer naar een logbestand (anders crasht print()).
    log = open(log_file(), "a", encoding="utf-8", buffering=1)
    if sys.stdout is None or getattr(sys, "frozen", False):
        sys.stdout = sys.stderr = log
    print(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} vanuit {base}")

    if already_running(PREFERRED_PORT):
        webbrowser.open(f"http://localhost:{PREFERRED_PORT}/")
        return

    prepare_environment(base)
    sys.path.insert(0, str(base))
    from werkzeug.serving import make_server

    from app import app  # pas importeren nadat de omgeving klaar is

    port = pick_port()
    server = make_server(HOST, port, app, threaded=True)
    app.config["SHUTDOWN"] = server.shutdown
    url = f"http://localhost:{port}/"
    print(f"draait op {url}")
    threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    finally:
        print("afgesloten")


if __name__ == "__main__":
    main()
