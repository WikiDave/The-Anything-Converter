"""Anything Converter - terminalversie (TUI).

Dezelfde ASCII-layout als de web-app, maar in je terminal: Windows Terminal/PowerShell, macOS/Linux
(bash, zsh) en via SSH op een server. Muis en toetsenbord werken allebei.

Start:  python tui.py [bestand]
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.theme import Theme
from textual.content import Content as E  # kale tekst: [ ... ] is geen opmaak
from textual.widgets import (Button, Checkbox, DirectoryTree, Footer, Input, Label, ProgressBar, RadioButton,
                             RadioSet, Select, Static, TabbedContent, TabPane)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from converter import settings as user_settings  # noqa: E402
from converter import virus  # noqa: E402
from converter.detect import LABELS, TARGETS, detect, extension, media_info  # noqa: E402
from converter.jobs import run_conversion  # noqa: E402
from converter.util import ConversionError, human_size, parse_size  # noqa: E402


def _version() -> str:
    exe = Path(sys.executable).resolve().parent
    for cand in (Path(__file__).resolve().parent / "VERSION", exe / "VERSION", exe.parent / "Resources" / "VERSION"):
        try:
            return cand.read_text().strip()
        except OSError:
            pass
    return "?"


VERSION = _version()

LOGO = r"""
 █████╗ ███╗   ██╗██╗   ██╗████████╗██╗  ██╗██╗███╗   ██╗ ██████╗
██╔══██╗████╗  ██║╚██╗ ██╔╝╚══██╔══╝██║  ██║██║████╗  ██║██╔════╝
███████║██╔██╗ ██║ ╚████╔╝    ██║   ███████║██║██╔██╗ ██║██║  ███╗
██╔══██║██║╚██╗██║  ╚██╔╝     ██║   ██╔══██║██║██║╚██╗██║██║   ██║
██║  ██║██║ ╚████║   ██║      ██║   ██║  ██║██║██║ ╚████║╚██████╔╝
╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝      ╚═╝   ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝
 ██████╗ ██████╗ ███╗   ██╗██╗   ██╗███████╗██████╗ ████████╗███████╗██████╗
██╔════╝██╔═══██╗████╗  ██║██║   ██║██╔════╝██╔══██╗╚══██╔══╝██╔════╝██╔══██╗
██║     ██║   ██║██╔██╗ ██║██║   ██║█████╗  ██████╔╝   ██║   █████╗  ██████╔╝
██║     ██║   ██║██║╚██╗██║╚██╗ ██╔╝██╔══╝  ██╔══██╗   ██║   ██╔══╝  ██╔══██╗
╚██████╗╚██████╔╝██║ ╚████║ ╚████╔╝ ███████╗██║  ██║   ██║   ███████╗██║  ██║
 ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝""".strip("\n")
LOGO_SMALL = "▄▀█ █▄ █ █▄█ ▀█▀ █ █ █ █▄ █ █▀▀   █▀▀ █▀█ █▄ █ █ █ █▀▀ █▀█ ▀█▀ █▀▀ █▀█\n" \
             "█▀█ █ ▀█  █   █  █▀█ █ █ ▀█ █▄█   █▄▄ █▄█ █ ▀█ ▀▄▀ ██▄ █▀▄  █  ██▄ █▀▄"


def _theme(name: str, fg: str, hi: str, dim: str) -> Theme:
    return Theme(name=name, primary=fg, secondary=dim, accent=hi, foreground=fg, background="#000000",
                 surface="#000000", panel="#0a0a0a", success=hi, warning="#ffb000", error="#ff5f56", dark=True,
                 variables={"block-cursor-foreground": "#000000", "block-cursor-background": fg,
                            "input-selection-background": f"{fg} 35%", "footer-key-foreground": hi,
                            "footer-description-foreground": dim, "border": dim, "border-blurred": dim})


THEMES = [_theme("ac-groen", "#a6ff5c", "#d9ffb8", "#5b8a3a"), _theme("ac-amber", "#ffb000", "#ffd98a", "#9a6c17"),
          _theme("ac-cyaan", "#5ff5d0", "#c4fff0", "#36897a")]

CSS = """
Screen { background: #000000; }
* { scrollbar-color: $secondary; scrollbar-background: #000000; }
#top { height: 1; color: $secondary; }
#top .name { color: $primary; width: auto; }
#logo { color: $primary; height: auto; margin: 1 0 0 0; }
#tagline { color: $secondary; margin: 0 0 1 0; }
#menubar { height: 3; border: solid $secondary; padding: 0 1; }
#menubar Label { width: auto; color: $secondary; padding: 0 1; margin: 0 3 0 0; }
#menubar Label.on { color: #000000; background: $primary; }
#menubar Label.done { color: $primary; }
.frame { border: solid $secondary; border-title-color: $accent; border-title-style: bold; padding: 0 1; height: auto; margin: 0 0 1 0; }
.prompt { color: $secondary; width: auto; padding: 1 1 0 0; }
.dim { color: $secondary; }
.row { height: auto; }
Input { background: #000000; border: tall $secondary; color: $accent; }
Input:focus { border: tall $primary; }
Select > SelectCurrent { background: #000000; border: tall $secondary; }
Select:focus > SelectCurrent { border: tall $primary; }
Button { background: #000000; color: $primary; border: none; min-width: 10; height: 1; margin: 1 1 0 0; text-style: none; }
Button:hover, Button:focus { background: $primary; color: #000000; text-style: bold; }
Button.go { width: 100%; height: 3; border: solid $primary; text-style: bold; }
RadioSet { background: #000000; border: none; height: auto; }
RadioButton, Checkbox { background: #000000; }
DirectoryTree { height: 14; background: #000000; border: solid $secondary; }
DirectoryTree:focus { border: solid $primary; }
ProgressBar { margin: 1 0 0 0; }
Bar > .bar--bar { color: $primary; background: #1a2712; }
Bar > .bar--complete { color: $accent; }
TabbedContent ContentTabs { background: #000000; }
Tab { color: $secondary; }
Tab.-active { color: $accent; text-style: bold; }
#result { border: solid $primary; padding: 0 1; height: auto; display: none; }
#result.show { display: block; }
#result.err { border: solid $error; color: $error; }
.cols { height: auto; }
.cols > Vertical { width: 1fr; height: auto; }
#status { dock: bottom; height: 1; color: $primary; background: #000000; padding: 0 1; }
"""


def bars(before: int, after: int, width: int = 26) -> str:
    m = max(before, after, 1)
    b = lambda n: "█" * max(1, round(n / m * width)) + "░" * (width - max(1, round(n / m * width)))  # noqa: E731
    d = (after - before) / before * 100 if before else 0
    arrow = "▼" if d <= 0 else "▲"
    return (f"ORIGINEEL  {b(before)} {human_size(before)}\n"
            f"NIEUW      {b(after)} {human_size(after)}\n"
            f"VERSCHIL   {arrow} {abs(d):.1f}% {'kleiner' if d <= 0 else 'groter'}")


class Converter(App):
    TITLE = "Anything Converter"
    CSS = CSS
    BINDINGS = [
        Binding("ctrl+s", "start", "start"),
        Binding("ctrl+t", "skin", "kleur"),
        Binding("ctrl+o", "focus_path", "pad"),
        Binding("ctrl+q", "quit", "afsluiten"),
    ]

    def __init__(self, start_file: str | None = None):
        super().__init__()
        self.src: Path | None = Path(start_file).expanduser().resolve() if start_file else None
        self.cancel = threading.Event()

    # ---------------------------------------------------------------- opbouw
    def compose(self) -> ComposeResult:
        with Horizontal(id="top"):
            yield Label("ANYTHING CONVERTER (TM)", classes="name")
            yield Label(f"   VER {VERSION} · TERMINAL   ctrl+t = kleur   ctrl+q = afsluiten", classes="dim")
        yield Static(LOGO, id="logo")
        yield Label("> converteer · verklein · vergroot · knip · links · torrents · viruscheck", id="tagline")
        with Horizontal(id="menubar"):
            for i, t in enumerate(("01 BESTAND", "02 FORMAAT", "03 GROOTTE", "04 UITVOER"), 1):
                yield Label(t, id=f"step{i}", classes="on" if i == 1 else "")
        with TabbedContent(initial="tab-convert"):
            with TabPane(E("[ CONVERTEREN ]"), id="tab-convert"):
                yield from self.compose_convert()
            with TabPane(E("[ LINK & TORRENT ]"), id="tab-fetch"):
                yield from self.compose_fetch()
            with TabPane(E("[ VIRUSSCAN ]"), id="tab-scan"):
                yield from self.compose_scan()
        yield Label("> gereed", id="status", markup=False)
        yield Footer()

    def compose_convert(self) -> ComposeResult:
        with VerticalScroll():
            with Vertical(classes="frame", id="f-file") as f:
                f.border_title = "BESTAND"
                with Horizontal(classes="row"):
                    yield Label("PAD>", classes="prompt")
                    yield Input(placeholder="typ of plak een pad, of kies hieronder", id="path")
                yield DirectoryTree(str(self.src.parent if self.src else Path.cwd()), id="tree")
                yield Label("// kies een bestand met de pijltjes en enter, of klik erop", id="fileinfo", markup=False, classes="dim")
            with Horizontal(classes="cols"):
                with Vertical(classes="frame") as f:
                    f.border_title = "FORMAAT"
                    yield Select([], prompt="eerst een bestand kiezen", id="format", allow_blank=True)
                    yield Label("UITVOER-MAP>", classes="prompt")
                    yield Input(placeholder="(zelfde map als het bestand)", id="outdir")
                with Vertical(classes="frame") as f:
                    f.border_title = "GROOTTE"
                    with RadioSet(id="mode"):
                        yield RadioButton("Kwaliteit", value=True, id="m-quality")
                        yield RadioButton("Doelgrootte", id="m-target")
                    with RadioSet(id="quality"):
                        yield RadioButton("Hoog", id="q-high")
                        yield RadioButton("Normaal", value=True, id="q-medium")
                        yield RadioButton("Laag", id="q-low")
                    with Horizontal(classes="row"):
                        yield Label("DOEL>", classes="prompt")
                        yield Input(placeholder="bijv. 8 MB of 500 KB", id="target")
            with Vertical(classes="frame", id="f-trim") as f:
                f.border_title = "KNIPPEN · VIDEO"
                with Horizontal(classes="row"):
                    yield Label("IN>", classes="prompt")
                    yield Input(placeholder="0:00", id="t-start")
                    yield Label("UIT>", classes="prompt")
                    yield Input(placeholder="einde", id="t-end")
                with Horizontal(classes="row"):
                    yield Label("RESOLUTIE>", classes="prompt")
                    yield Select([(f"{h}p", str(h)) for h in (2160, 1440, 1080, 720, 480, 360)],
                                 prompt="origineel / automatisch", id="height", allow_blank=True)
                    yield Checkbox("Geluid verwijderen", id="noaudio")
            yield Button(E("[ ▶ START ]  (ctrl+s)"), id="go", classes="go")
            yield ProgressBar(total=100, show_eta=False, id="progress")
            yield Static("", id="result", markup=False)

    def compose_fetch(self) -> ComposeResult:
        with VerticalScroll():
            with Vertical(classes="frame") as f:
                f.border_title = "LINK · MAGNET · .TORRENT"
                with Horizontal(classes="row"):
                    yield Label("LINK>", classes="prompt")
                    yield Input(placeholder="https://www.youtube.com/watch?v=…  of  magnet:?…  of pad naar .torrent",
                                id="url")
                with Horizontal(classes="row"):
                    yield Checkbox("Alleen geluid", id="audio")
                    yield Checkbox("Controleren op virussen", value=True, id="scan")
                with Horizontal(classes="row"):
                    yield Label("OPSLAAN IN>", classes="prompt")
                    yield Input(value=str(Path.home() / "Downloads"), id="dl-dir")
                with Horizontal(classes="row"):
                    yield Button(E("[ OPHALEN ]"), id="fetch")
                    yield Button(E("[ STOP ]"), id="stop")
                yield ProgressBar(total=100, show_eta=False, id="f-progress")
                yield Static("// alleen voor eigen bestanden, vrije licenties of met toestemming van de maker.",
                             id="f-result", markup=False, classes="dim")

    def compose_scan(self) -> ComposeResult:
        with VerticalScroll():
            with Vertical(classes="frame") as f:
                f.border_title = "VIRUSSCAN"
                with Horizontal(classes="row"):
                    yield Label("PAD>", classes="prompt")
                    yield Input(placeholder="bestand of map", id="scan-path")
                    yield Button(E("[ SCANNEN ]"), id="scan-go")
                yield Static("", id="scan-result", markup=False)
            with Vertical(classes="frame") as f:
                f.border_title = "VIRUSTOTAL (OPTIONEEL)"
                with Horizontal(classes="row"):
                    yield Label("SLEUTEL>", classes="prompt")
                    yield Input(password=True, placeholder="gratis api-sleutel van virustotal.com", id="vt")
                    yield Button(E("[ OPSLAAN ]"), id="vt-save")
                yield Label("", id="scanner-info", markup=False, classes="dim")

    def on_mount(self) -> None:
        for t in THEMES:
            self.register_theme(t)
        try:
            skin = user_settings.load().get("tui_skin", "ac-groen")
        except Exception:
            skin = "ac-groen"
        self.theme = skin if skin in [t.name for t in THEMES] else "ac-groen"
        self.query_one("#progress", ProgressBar).display = False
        self.query_one("#f-progress", ProgressBar).display = False
        self.query_one("#f-trim").display = False
        eng = virus.available_engine()
        self.query_one("#scanner-info", Label).update(
            f"// scanner op deze computer: {eng}" if eng else
            "// geen scanner gevonden. windows: defender staat er standaard op. mac/linux: installeer clamav.")
        self.fit_logo(self.size.width)
        if self.src:
            self.choose(self.src)

    def on_resize(self, event) -> None:
        self.fit_logo(event.size.width)

    def fit_logo(self, width: int) -> None:
        logo = self.query_one("#logo", Static)
        logo.update(LOGO if width >= 82 else LOGO_SMALL if width >= 74 else "ANYTHING CONVERTER")

    # ---------------------------------------------------------------- hulpjes
    def status(self, msg: str) -> None:
        self.query_one("#status", Label).update("> " + msg)

    def step(self, n: int) -> None:
        for i in range(1, 5):
            lbl = self.query_one(f"#step{i}", Label)
            lbl.set_class(i == n or (n == 2 and i == 3), "on")
            lbl.set_class(i < n, "done")

    def action_skin(self) -> None:
        names = [t.name for t in THEMES]
        self.theme = names[(names.index(self.theme) + 1) % len(names)] if self.theme in names else names[0]
        try:
            s = user_settings.load(); s["tui_skin"] = self.theme; user_settings.save(s)
        except Exception:
            pass

    def action_focus_path(self) -> None:
        self.query_one(TabbedContent).active = "tab-convert"
        self.query_one("#path", Input).focus()

    # ---------------------------------------------------------------- bestand kiezen
    @on(DirectoryTree.FileSelected, "#tree")
    def tree_pick(self, event: DirectoryTree.FileSelected) -> None:
        self.choose(Path(event.path))

    @on(Input.Submitted, "#path")
    def path_typed(self, event: Input.Submitted) -> None:
        p = Path(event.value.strip().strip('"').strip("'")).expanduser()
        if p.is_dir():
            self.query_one("#tree", DirectoryTree).path = p
        elif p.is_file():
            self.choose(p.resolve())
        else:
            self.status("bestaat niet: " + event.value)

    def choose(self, path: Path) -> None:
        if not path.is_file():
            return
        self.src = path
        cat = detect(path)
        self.cat = cat
        info = media_info(path) if cat in ("video", "audio", "image") else {}
        meta = [LABELS[cat], human_size(path.stat().st_size)]
        if info.get("width"):
            meta.append(f"{info['width']}×{info['height']}")
        if info.get("duration") and cat != "image":
            meta.append(f"{int(info['duration'] // 60)}:{info['duration'] % 60:04.1f}")
        self.query_one("#fileinfo", Label).update(f"NAAM  {path.name}\nINFO  {' · '.join(meta)}")
        self.query_one("#path", Input).value = str(path)
        targets = TARGETS[cat]
        ext = extension(path)
        sel = self.query_one("#format", Select)
        sel.set_options([(f".{t}" + ("  (zelfde formaat)" if t == ext else ""), t) for t in targets])
        sel.value = ext if ext in targets else targets[0]
        self.query_one("#f-trim").display = cat in ("video", "audio")
        self.step(2)
        self.status(f"geladen: {path.name} [{LABELS[cat].lower()}]")

    # ---------------------------------------------------------------- converteren
    def action_start(self) -> None:
        if self.query_one(TabbedContent).active == "tab-convert":
            self.start_convert()

    @on(Button.Pressed, "#go")
    def go_pressed(self) -> None:
        self.start_convert()

    def options(self) -> dict:
        opts: dict = {}
        fmt = self.query_one("#format", Select).value
        if isinstance(fmt, str):
            opts["format"] = fmt
        if self.query_one("#m-target", RadioButton).value:
            raw = self.query_one("#target", Input).value.strip()
            if not raw:
                raise ConversionError("Vul een doelgrootte in, bijvoorbeeld 8 MB of 500 KB.")
            opts["target_bytes"] = parse_size(raw, "mb")
        else:
            q = self.query_one("#quality", RadioSet).pressed_button
            opts["quality"] = {"q-high": "high", "q-low": "low"}.get(q.id if q else "", "medium")
        if self.cat in ("video", "audio"):
            for key, wid in (("trim_start", "#t-start"), ("trim_end", "#t-end")):
                v = self.query_one(wid, Input).value.strip()
                if v:
                    opts[key] = v
            h = self.query_one("#height", Select).value
            if isinstance(h, str):
                opts["height"] = int(h)
            if self.query_one("#noaudio", Checkbox).value:
                opts["remove_audio"] = True
        return opts

    def start_convert(self) -> None:
        res = self.query_one("#result", Static)
        if not self.src:
            res.set_classes("show err"); res.update("!! FOUT\nKies eerst een bestand."); return
        try:
            opts = self.options()
        except ConversionError as exc:
            res.set_classes("show err"); res.update(f"!! FOUT\n{exc}"); return
        out_dir = self.query_one("#outdir", Input).value.strip() or str(self.src.parent)
        self.query_one("#go", Button).disabled = True
        self.query_one("#progress", ProgressBar).display = True
        res.set_classes(""); self.step(4)
        self.convert_worker(self.src, Path(out_dir).expanduser(), self.cat, opts)

    @work(thread=True, exclusive=True)
    def convert_worker(self, src: Path, out_dir: Path, cat: str, opts: dict) -> None:
        bar = self.query_one("#progress", ProgressBar)

        def progress(f: float, msg: str) -> None:
            self.call_from_thread(bar.update, progress=round(f * 100, 1))
            self.call_from_thread(self.status, f"{msg.lower()} {round(f * 100)}%")

        tmp = Path(tempfile.mkdtemp(prefix="ac-tui-"))
        try:
            made = run_conversion(src, tmp, cat, opts, progress)
            out_dir.mkdir(parents=True, exist_ok=True)
            dst = out_dir / made.name
            n = 2
            while dst.exists():
                dst = out_dir / f"{made.stem}_{n}{made.suffix}"; n += 1
            shutil.move(str(made), dst)
            text = f"STATUS: OK\nBESTAND    {dst}\n" + bars(src.stat().st_size, dst.stat().st_size)
            self.call_from_thread(self.show_result, text, False)
            self.call_from_thread(self.status, f"klaar: {dst.name} ({human_size(dst.stat().st_size)})")
        except ConversionError as exc:
            self.call_from_thread(self.show_result, f"!! FOUT\n{exc}", True)
        except Exception as exc:  # onverwacht
            self.call_from_thread(self.show_result, f"!! FOUT\nEr ging iets mis: {exc}", True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            self.call_from_thread(self.done_convert)

    def show_result(self, text: str, err: bool) -> None:
        res = self.query_one("#result", Static)
        res.set_classes("show err" if err else "show")
        res.update(text)

    def done_convert(self) -> None:
        self.query_one("#go", Button).disabled = False
        self.query_one("#progress", ProgressBar).display = False
        self.step(2)

    # ---------------------------------------------------------------- link & torrent
    @on(Button.Pressed, "#fetch")
    def fetch_pressed(self) -> None:
        src = self.query_one("#url", Input).value.strip()
        if not src:
            return
        self.cancel.clear()
        self.query_one("#fetch", Button).disabled = True
        self.query_one("#f-progress", ProgressBar).display = True
        self.fetch_worker(src, Path(self.query_one("#dl-dir", Input).value).expanduser(),
                          self.query_one("#audio", Checkbox).value, self.query_one("#scan", Checkbox).value)

    @on(Button.Pressed, "#stop")
    def stop_pressed(self) -> None:
        self.cancel.set()

    @work(thread=True, exclusive=True, group="fetch")
    def fetch_worker(self, src: str, dl_dir: Path, audio: bool, scan: bool) -> None:
        from converter import fetch, torrent
        bar = self.query_one("#f-progress", ProgressBar)
        out = self.query_one("#f-result", Static)

        def progress(f: float, msg: str) -> None:
            self.call_from_thread(bar.update, progress=round(f * 100, 1))
            self.call_from_thread(out.update, "> " + msg.lower())

        try:
            dl_dir.mkdir(parents=True, exist_ok=True)
            if src.lower().startswith("magnet:?") or src.lower().endswith(".torrent"):
                source = Path(src).expanduser().read_bytes() if src.lower().endswith(".torrent") else src
                res = torrent.download(source, dl_dir, progress, cancelled=self.cancel.is_set)
                target = dl_dir / res["files"][0]["path"] if len(res["files"]) == 1 else dl_dir / res["name"]
                lines = [f"TORRENT KLAAR: {res['name']} · {len(res['files'])} bestanden"]
                for i, fl in enumerate(res["files"][:40]):
                    lines.append(f"{'└─' if i == len(res['files']) - 1 else '├─'} {fl['path']}  {human_size(fl['size'])}")
            else:
                target = fetch.download(src, dl_dir, audio, progress)
                lines = [f"OPGEHAALD: {target}"]
            if scan:
                progress(0.995, "controleren op virussen")
                v = virus.check(target, user_settings.load().get("vt_key"))
                lines.append(self.virus_line(v))
                if v["status"] == "infected":
                    lines.append("!! niet openen. verwijder dit bestand.")
            self.call_from_thread(out.update, "\n".join(lines))
            if target.is_file() and not (scan and v["status"] == "infected"):
                self.call_from_thread(self.choose, target)
                self.call_from_thread(lambda: setattr(self.query_one(TabbedContent), "active", "tab-convert"))
        except ConversionError as exc:
            self.call_from_thread(out.update, f"!! {exc}")
        except Exception as exc:
            self.call_from_thread(out.update, f"!! er ging iets mis: {exc}")
        finally:
            self.call_from_thread(lambda: setattr(self.query_one("#fetch", Button), "disabled", False))
            self.call_from_thread(lambda: setattr(bar, "display", False))

    # ---------------------------------------------------------------- virusscan
    @staticmethod
    def virus_line(v: dict) -> str:
        loc = v["local"]
        vt = next((f["vt"]["detail"] for f in v.get("files", []) if f.get("vt")), None)
        extra = f" · virustotal: {vt}" if vt else ""
        if v["status"] == "infected":
            return f"!! VIRUS GEVONDEN ({loc.get('engine')}): {loc.get('detail')}{extra}"
        if v["status"] == "clean":
            return f"✓ geen virus gevonden ({loc.get('engine')}){extra}"
        return f"? niet zeker: {loc.get('detail')}{extra}"

    @on(Button.Pressed, "#scan-go")
    @on(Input.Submitted, "#scan-path")
    def scan_pressed(self) -> None:
        p = Path(self.query_one("#scan-path", Input).value.strip().strip('"')).expanduser()
        out = self.query_one("#scan-result", Static)
        if not p.exists():
            out.update("!! bestaat niet"); return
        out.update("> scannen…")
        self.scan_worker(p)

    @work(thread=True, group="scan")
    def scan_worker(self, p: Path) -> None:
        v = virus.check(p, user_settings.load().get("vt_key"))
        lines = [self.virus_line(v)] + [f"sha-256 {f['sha256']}  {f['name']}\n        {f['virustotal']}" for f in v["files"][:5]]
        self.call_from_thread(self.query_one("#scan-result", Static).update, "\n".join(lines))

    @on(Button.Pressed, "#vt-save")
    def vt_save(self) -> None:
        key = self.query_one("#vt", Input).value.strip()
        if key and (len(key) != 64 or any(c not in "0123456789abcdefABCDEF" for c in key)):
            self.query_one("#scanner-info", Label).update("!! een virustotal-sleutel heeft 64 tekens (0-9, a-f)")
            return
        s = user_settings.load(); s["vt_key"] = key; user_settings.save(s)
        self.query_one("#vt", Input).value = ""
        self.query_one("#scanner-info", Label).update("// sleutel opgeslagen ✓" if key else "// sleutel verwijderd")


def main() -> None:
    ap = argparse.ArgumentParser(prog="anything-converter-tui", description="Anything Converter in de terminal")
    ap.add_argument("bestand", nargs="?", help="bestand om direct te openen")
    ap.add_argument("--version", action="store_true", help="versie tonen")
    args = ap.parse_args()
    if args.version:
        print(f"Anything Converter {VERSION} (terminal)")
        return
    # meegeleverde programma's (ffmpeg, deno) in de desktop-installatie
    here = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    for bindir in (here / "bin", here.parent / "Resources" / "bin"):  # macOS .app: ook Resources
        if bindir.is_dir():
            os.environ["PATH"] = str(bindir) + os.pathsep + os.environ.get("PATH", "")
            break
    Converter(args.bestand).run()


if __name__ == "__main__":
    main()
