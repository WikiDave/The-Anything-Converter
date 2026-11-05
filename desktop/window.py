"""Eigen programmavenster voor de desktop-app (pywebview): geen browser, geen adresbalk.

Gebruikt alleen de standaardbibliotheek en pywebview, zodat dit bestand op Linux ook los met de
systeem-Python kan draaien (die heeft de GTK/WebKit-koppeling):

    python3 window.py <url> [opslagmap] [icoon]

Het venster praat met de lokale converter-server via HTTP. Opslaan gaat via een echt
"Bewaar als"-venster van het besturingssysteem, links naar buiten openen in de gewone browser.
"""
from __future__ import annotations

import base64
import re
import sys
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
if (HERE / "pyweb").is_dir():  # Linux: meegeleverde pywebview-bronbestanden
    sys.path.insert(0, str(HERE / "pyweb"))

TITLE = "Anything Converter"
SIZE = (1280, 860)
MIN_SIZE = (760, 560)


def _filename(headers, fallback: str) -> str:
    cd = headers.get("Content-Disposition") or ""
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.I)
    if m:
        return urllib.parse.unquote(m.group(1))
    m = re.search(r'filename="?([^";]+)"?', cd, re.I)
    return m.group(1) if m else fallback


def _downloads() -> str:
    d = Path.home() / "Downloads"
    return str(d if d.is_dir() else Path.home())


class Api:
    """Functies die de pagina aanroept via window.pywebview.api.*"""

    def __init__(self, base: str):
        p = urllib.parse.urlparse(base)
        self._base = f"{p.scheme}://{p.netloc}"
        self._out = None
        self._target = None

    def _ask(self, name: str):
        import webview
        win = webview.active_window() or webview.windows[0]
        dialog = getattr(webview, "FileDialog", None)
        kind = dialog.SAVE if dialog else webview.SAVE_DIALOG
        res = win.create_file_dialog(kind, directory=_downloads(), save_filename=name)
        if not res:
            return None
        return res if isinstance(res, str) else res[0]

    def save_url(self, path: str):
        """Bestand van de lokale server opslaan (resultaat, origineel, torrent-bestand)."""
        if not isinstance(path, str) or not path.startswith("/"):
            return {"error": "invalid path"}
        try:
            with urllib.request.urlopen(self._base + path, timeout=60) as r:
                name = _filename(r.headers, Path(urllib.parse.urlparse(path).path).name or "bestand")
                target = self._ask(name)
                if not target:
                    return {"cancelled": True}
                with open(target, "wb") as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
            return {"path": target}
        except Exception as e:  # noqa: BLE001 - melding gaat naar de pagina
            return {"error": str(e)}

    # Opslaan van iets dat in de pagina zelf gemaakt is (PDF- en archief-werkbank), in stukjes.
    def save_begin(self, name: str):
        self.save_abort()
        target = self._ask(str(name or "bestand"))
        if not target:
            return {"cancelled": True}
        try:
            self._out = open(target, "wb")
        except OSError as e:
            return {"error": str(e)}
        self._target = target
        return {"path": target}

    def save_chunk(self, data: str):
        if not self._out:
            return False
        self._out.write(base64.b64decode(data))
        return True

    def save_end(self):
        if not self._out:
            return {"error": "nothing to save"}
        self._out.close()
        self._out = None
        return {"path": self._target}

    def save_abort(self):
        if self._out:
            self._out.close()
            self._out = None
            try:
                Path(self._target).unlink()
            except OSError:
                pass

    def open_external(self, url: str):
        if isinstance(url, str) and url.split(":", 1)[0].lower() in ("http", "https", "mailto"):
            webbrowser.open(url)
            return True
        return False

    def open_window(self, path: str):
        """Tweede venster, bijv. de PDF- en archief-werkbank."""
        import webview
        if not isinstance(path, str) or not path.startswith("/"):
            return False
        title = TITLE + (" - PDF & archive" if path.startswith("/web/") else "")
        webview.create_window(title, self._base + path, js_api=self, width=SIZE[0], height=SIZE[1],
                              min_size=MIN_SIZE, background_color="#000000", text_select=True)
        return True


def check() -> str:
    """Kan er een venster gemaakt worden? Geeft de gebruikte techniek terug of gooit een fout."""
    import webview  # noqa: F401
    if sys.platform == "win32":
        from webview.platforms import winforms
        if winforms.renderer != "edgechromium":
            raise RuntimeError("WebView2 is missing")
        return "edgechromium"
    if sys.platform == "darwin":
        import WebKit  # noqa: F401
        return "cocoa"
    import gi
    gi.require_version("Gtk", "3.0")
    try:
        gi.require_version("WebKit2", "4.1")
    except ValueError:
        gi.require_version("WebKit2", "4.0")
    from gi.repository import Gtk, WebKit2  # noqa: F401
    return "gtk"


def run(url: str, storage: str | None = None, icon: str | None = None, on_start=None) -> None:
    """Toont het venster en komt terug als de gebruiker het sluit."""
    import webview
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    webview.create_window(TITLE, url, js_api=Api(url), width=SIZE[0], height=SIZE[1], min_size=MIN_SIZE,
                          background_color="#000000", text_select=True)
    gui = {"win32": "edgechromium", "darwin": "cocoa"}.get(sys.platform, "gtk")
    kwargs = {"gui": gui, "private_mode": False}
    if storage:
        kwargs["storage_path"] = storage
    if icon and gui == "gtk":
        kwargs["icon"] = icon
    webview.start(on_start, **kwargs)


def close_all() -> None:
    import webview
    for w in list(webview.windows):
        try:
            w.destroy()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        print(check())
        sys.exit(0)
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None, sys.argv[3] if len(sys.argv) > 3 else None)
