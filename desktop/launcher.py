"""Anything Converter - desktop-app.

Start de converter op de achtergrond en toont hem in een eigen programmavenster (pywebview:
WebView2 op Windows, WebKit op macOS en Linux), zonder browser of adresbalk. Venster dicht =
programma af. Lukt een eigen venster niet, dan een los app-venster van Edge/Chrome, en als
laatste redmiddel de gewone browser (met [ AFSLUITEN ] bovenaan).
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
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


def data_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AnythingConverter"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "AnythingConverter"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "AnythingConverter"
    root.mkdir(parents=True, exist_ok=True)
    return root


def app_browser() -> str | None:
    """Edge/Chrome/Chromium/Brave: die kunnen een los app-venster zonder adresbalk tonen."""
    if sys.platform == "win32":
        cands = [Path(os.environ.get(v, "")) / sub for v in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")
                 for sub in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe")]
    elif sys.platform == "darwin":
        cands = [Path(f"/Applications/{a}.app/Contents/MacOS/{a}")
                 for a in ("Google Chrome", "Microsoft Edge", "Chromium", "Brave Browser")]
    else:
        cands = [shutil.which(n) for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                                            "microsoft-edge", "brave-browser")]
    for c in cands:
        if c and os.path.isfile(c):
            return str(c)
    return None


def native_window(url: str, base: Path, closers: list) -> bool:
    """Eigen programmavenster. Geeft True terug nadat het venster gesloten is."""
    sys.path.insert(0, str(base))
    try:
        import window
        engine = window.check()
    except Exception as e:  # noqa: BLE001
        print("own window in this process failed:", repr(e))
        engine = None
    storage = str(data_dir() / "webview")
    icon = str(base / "icon-512.png")
    if engine:
        print("venster:", engine)
        closers.append(window.close_all)
        from app import app as flask_app
        flask_app.config["FOCUS"] = window.focus
        window.run(url, storage, icon)
        return True
    # Linux: de systeem-Python heeft de GTK/WebKit-koppeling; pywebview zit als bronbestanden in pyweb/.
    helper = base / "window.py"
    if not (sys.platform.startswith("linux") and (base / "pyweb").is_dir()):
        return False
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    for py in system_pythons():
        try:
            ok = subprocess.run([py, "-I", str(helper), "--check"], env=env, capture_output=True, text=True,
                                timeout=30)
        except Exception as e:  # noqa: BLE001
            print(py, "faalde:", repr(e))
            continue
        if ok.returncode != 0:
            print(py, "has no GTK/WebKit:", (ok.stderr or "").strip()[-300:])
            continue
        print("venster: gtk via", py)
        proc = subprocess.Popen([py, "-I", str(helper), url, storage, icon], env=env)
        closers.append(proc.terminate)
        proc.wait()
        return True
    return False


def system_pythons() -> list[str]:
    """Python-versies van het systeem; python3-gi hoort bij de standaardversie van de distributie."""
    import glob
    found = ["/usr/bin/python3", shutil.which("python3") or ""]
    found += sorted((p for p in glob.glob("/usr/bin/python3.[0-9]*") if p[-1].isdigit()), reverse=True)
    out = []
    for p in found:
        if p and os.path.isfile(p) and os.path.realpath(p) not in (os.path.realpath(x) for x in out):
            out.append(p)
    return out


def browser_app_window(url: str, closers: list) -> bool:
    exe = app_browser()
    if not exe:
        return False
    profile = data_dir() / "app-venster"
    args = [exe, f"--app={url}", f"--user-data-dir={profile}", "--window-size=1280,860", "--no-first-run",
            "--no-default-browser-check"]
    print("window: app mode of", exe)
    t0 = time.time()
    proc = subprocess.Popen(args)
    closers.append(proc.terminate)
    proc.wait()
    # Binnen een paar seconden terug: overgedragen aan een al draaiend exemplaar of mislukt.
    return time.time() - t0 > 5


def ensure_on_path(base: Path) -> None:
    """Windows: put the install folder in the user's PATH so 'anything-converter-tui' works in every
    new terminal, also when the installer's PATH entry got lost (or the app was copied by hand)."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    if not (base / "anything-converter-tui.exe").exists():
        return
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                value, kind = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                value, kind = "", winreg.REG_EXPAND_SZ
            parts = [x for x in value.split(";") if x]
            if any(os.path.normcase(os.path.expandvars(x)).rstrip("\\") == os.path.normcase(str(base)).rstrip("\\")
                   for x in parts):
                return
            winreg.SetValueEx(key, "Path", 0, kind, ";".join(parts + [str(base)]))
        import ctypes  # tell running programs (Explorer) that the environment changed
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 2, 2000, None)
        print("added to PATH:", base)
    except Exception as e:  # noqa: BLE001
        print("could not add to PATH:", e)


def instance_file() -> Path:
    return data_dir() / "instance.json"


def hand_over(files: list[str]) -> bool:
    """Is the app already open? Then give it these files and stop (no second window)."""
    try:
        inst = json.loads(instance_file().read_text(encoding="utf-8"))
        port = int(inst["port"])
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/ping", timeout=2) as r:
            if json.load(r).get("app") != "anything-converter":
                return False
        req = urllib.request.Request(f"http://{HOST}:{port}/api/open", data=json.dumps({"paths": files}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            return bool(json.load(r).get("ok"))
    except Exception:  # noqa: BLE001 - no running app (or an old one): start normally
        return False


def main() -> None:
    base = app_dir()
    # "Open with" / right-click: the files come as arguments
    files = [str(Path(a).resolve()) for a in sys.argv[1:] if not a.startswith("-") and Path(a).is_file()]
    if files and hand_over(files):
        return
    # Een GUI-app heeft geen console: schrijf uitvoer naar een logbestand (anders crasht print()).
    log = open(log_file(), "a", encoding="utf-8", buffering=1)
    if sys.stdout is None or getattr(sys, "frozen", False):
        sys.stdout = sys.stderr = log
    print(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} vanuit {base}")

    prepare_environment(base)
    ensure_on_path(base)
    sys.path.insert(0, str(base))
    from werkzeug.serving import make_server

    from app import app  # pas importeren nadat de omgeving klaar is

    port = pick_port()
    server = make_server(HOST, port, app, threaded=True)
    url = f"http://{HOST}:{port}/"
    print(f"running at {url}")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    import app as app_module
    app_module.PENDING.extend(files)
    try:
        instance_file().write_text(json.dumps({"port": port, "pid": os.getpid()}), encoding="utf-8")
    except OSError:
        pass

    closers: list = []
    stopped = threading.Event()

    def shutdown():
        for close in closers:
            try:
                close()
            except Exception:  # noqa: BLE001
                pass
        stopped.set()

    app.config["SHUTDOWN"] = shutdown
    # ANYTHING_WINDOW=browser: altijd de gewone browser (bijv. voor testen)
    mode = os.environ.get("ANYTHING_WINDOW", "")
    shown = False
    for name, attempt in (("native", lambda: native_window(url, base, closers)),
                          ("app", lambda: browser_app_window(url, closers))):
        if mode in ("", name):
            app.config["WINDOW"] = name
            try:
                shown = attempt()
            except Exception as e:  # noqa: BLE001
                print(f"{name} window failed:", repr(e))
            if shown or stopped.is_set():
                break
            closers.clear()
    if not shown and not stopped.is_set():
        app.config["WINDOW"] = "browser"
        webbrowser.open(url)
        stopped.wait()
    server.shutdown()
    try:
        if json.loads(instance_file().read_text(encoding="utf-8")).get("pid") == os.getpid():
            instance_file().unlink()
    except (OSError, ValueError):
        pass
    print("closed")
    log.flush()
    os._exit(0)  # ook achtergrondtaken (downloads, torrents) stoppen


if __name__ == "__main__":
    main()
