"""Anything Converter - terminalversie.

Volledig scherm (Textual) met dezelfde ASCII-stijl als de web-app: Windows Terminal, PowerShell, cmd,
macOS Terminal/iTerm, Linux-terminals, tmux/screen en via SSH. Muis en toetsenbord werken allebei.
Kan de terminal dat niet aan (geen echte terminal, TERM=dumb, invoer via een pijp), dan start de
eenvoudige modus met genummerde menu's. Daarnaast zijn er opdrachten voor scripts.

Start:  python tui.py [bestand]          volledig scherm
        python tui.py --simpel           eenvoudige modus (elke terminal)
        python tui.py --ascii            alleen ASCII-tekens (oude consoles)
        python tui.py converteer a.mov --naar mp4      (zie --help)
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from converter import cli  # noqa: E402
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
# 3 lines of box-drawing characters: crisp in every terminal font (the old 2-line pixel font looked blurry)
LOGO_SMALL = (
    "┏━┓ ┏┓╻ ╻ ╻ ╺┳╸ ╻ ╻ ╻ ┏┓╻ ┏━╸    ┏━╸ ┏━┓ ┏┓╻ ╻ ╻ ┏━╸ ┏━┓ ╺┳╸ ┏━╸ ┏━┓\n"
    "┣━┫ ┃┗┫ ┗┳┛  ┃  ┣━┫ ┃ ┃┗┫ ┃╺┓    ┃   ┃ ┃ ┃┗┫ ┃┏┛ ┣╸  ┣┳┛  ┃  ┣╸  ┣┳┛\n"
    "╹ ╹ ╹ ╹  ╹   ╹  ╹ ╹ ╹ ╹ ╹ ┗━┛    ┗━╸ ┗━┛ ╹ ╹ ┗┛  ┗━╸ ╹┗╸  ╹  ┗━╸ ╹┗╸"
)
LOGO_ASCII = r"""
   _              _   _     _                  ___                     _
  /_\  _ _ _  _ _| |_| |_  (_)_ _  __ _       / __|___ _ ___ _____ _ _| |_ ___ _ _
 / _ \| ' \ || |  _| ' \ | | ' \/ _` |     | (__/ _ \ ' \ V / -_) '_|  _/ -_) '_|
/_/ \_\_||_\_, |\__|_||_||_|_||_\__, |      \___\___/_||_\_/\___|_|  \__\___|_|
           |__/                 |___/""".strip("\n")

# Gereedschap: (icoon links, icoon rechts, naam, actie, waarde)
TOOLS = [
    ("PDF", "DOC", "PDF to Word", "fmt", "docx"), ("PDF", "XLS", "PDF to Excel", "fmt", "xlsx"),
    ("PDF", "PPT", "PDF to PPT", "fmt", "pptx"), ("PDF", "PNG", "PDF to PNG", "fmt", "png"),
    ("PDF", "JPG", "PDF to JPEG", "fmt", "jpg"), ("PDF", "TXT", "PDF to TXT", "fmt", "txt"),
    ("PDF", "RTF", "PDF to RTF", "fmt", "rtf"), ("PDF", "HTM", "PDF to HTML", "fmt", "html"),
    ("PDF", "XML", "PDF to XML", "fmt", "xml"), ("DOC", "PDF", "Word to PDF", "fmt", "pdf"),
    ("XLS", "PDF", "Excel to PDF", "fmt", "pdf"), ("PPT", "PDF", "PPT to PDF", "fmt", "pdf"),
    ("IMG", "PDF", "Image to PDF", "fmt", "pdf"), ("TXT", "PDF", "TXT/RTF to PDF", "fmt", "pdf"),
    ("PDF", "+", "Merge PDFs", "tab", "tab-pdf"), ("PDF", "/", "Split PDF", "tab", "tab-pdf"),
    ("PDF", "v", "PDF comprimeren", "fmt", "pdf"), ("IMG", "TXT", "Bestands-OCR", "fmt", "txt"),
    ("[ ]", "TXT", "Screenshot-OCR", "screen", ""), ("~", "TXT", "Audio/video to text", "fmt", "txt"),
    ("~", "SRT", "Make subtitles", "fmt", "srt"), ("DOC", "EPUB", "E-book maken", "fmt", "epub"),
    ("EPUB", "AZW", "E-book for Kindle", "fmt", "azw3"), ("~", "M4R", "iPhone ringtone", "fmt", "m4r"),
    ("IMG", "IG", "Social media size", "tab", "tab-social"), ("WWW", "PDF", "Save website", "web", ""),
    ("BIN", "ISO", "CUE/BIN to ISO", "fmt", "iso"), ("BIN", "1x", "Merge BIN tracks", "fmt", "cue"),
    ("ISO", "CHD", "To CHD", "fmt", "chd"), ("ISO", "CSO", "PSP ISO to CSO", "fmt", "cso"),
    ("ROM", "IPS", "ROM patchen", "fmt", "patch"), ("N64", "Z64", "Convert N64 ROM", "fmt", "z64"),
    ("#", "SHA", "Checksum / hash", "tab", "tab-check"), ("ZIP", "7Z", "Archive", "tab", "tab-arch"),
    ("URL", "MP4", "Video link / torrent", "tab", "tab-fetch"), ("!", "AV", "Virus scan", "tab", "tab-check"),
    ("TXT", "ED", "Edit text", "tab", "tab-edit"), ("SQL", "DB", "Database viewer / SQL", "tab", "tab-db"),
]


COLOUR_PRESETS = [
    ("green phosphor", "#a6ff5c", "#000000"), ("amber", "#ffb000", "#000000"), ("cyan", "#5ff5d0", "#000000"),
    ("white", "#e8e8e8", "#000000"), ("matrix", "#00ff41", "#0d0208"), ("red alert", "#ff5555", "#120000"),
    ("pink", "#ff79c6", "#1a0b14"), ("purple", "#c792ea", "#120b1a"), ("ice", "#9fdcff", "#04121c"),
    ("gold", "#ffd700", "#161200"), ("dos", "#d0d0d0", "#0000a8"), ("c64", "#a5a5ff", "#40318d"),
    ("solarized", "#93a1a1", "#002b36"), ("gruvbox", "#ebdbb2", "#282828"), ("nord", "#d8dee9", "#2e3440"),
    ("dracula", "#f8f8f2", "#282a36"), ("high contrast", "#ffff00", "#000000"), ("paper", "#1a1a1a", "#f4f1e8"),
    ("sepia", "#5b4636", "#f4ecd8"), ("green on white", "#0b6b00", "#f3fff0"),
]


def build_app(ascii_mode: bool = False):
    """Bouwt de Textual-app. Apart, zodat de eenvoudige modus zonder Textual kan starten."""
    from textual import on, work
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
    from textual.content import Content as E  # kale tekst: [ ... ] is geen opmaak
    from textual.screen import ModalScreen
    from textual.theme import Theme
    from textual.widgets import (Button, Checkbox, DataTable, DirectoryTree, Footer, Input, Label, OptionList,
                                 ProgressBar, RadioButton, RadioSet, Select, Static, TabbedContent, TabPane, TextArea)

    from converter import settings as user_settings
    from converter import social, virus
    from converter.formats import analyse, fmt_label
    from converter.jobs import run_conversion

    A = cli.t if ascii_mode else (lambda s: s)  # tekst ASCII-veilig maken

    class Files(DirectoryTree):
        """Mappenlijst zonder emoji (die verschuiven in veel terminals), en in ASCII-modus zonder lijntjes."""
        ICON_NODE = "+ " if ascii_mode else "▸ "
        ICON_NODE_EXPANDED = "- " if ascii_mode else "▾ "
        ICON_FILE = "  "
        if ascii_mode:
            LINES = {k: ("  ", "| ", "`-", "|-") for k in ("default", "bold", "double")}

    if ascii_mode:
        RadioButton.BUTTON_INNER = "*"
        RadioButton.BUTTON_LEFT = "("
        RadioButton.BUTTON_RIGHT = ")"
        Checkbox.BUTTON_INNER = "x"
        Checkbox.BUTTON_LEFT = "["
        Checkbox.BUTTON_RIGHT = "]"

    def _mix(a: str, b: str, t: float) -> str:
        ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
        cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
        return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))

    def _light(c: str) -> bool:
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b > 140

    def theme(name: str, fg: str, bg: str = "#000000") -> Theme:
        light = _light(bg)
        hi = _mix(fg, "#000000" if light else "#ffffff", 0.5)
        dim = _mix(fg, bg, 0.45)
        return Theme(name=name, primary=fg, secondary=dim, accent=hi, foreground=fg, background=bg,
                     surface=bg, panel=_mix(fg, bg, 0.92), success=hi, warning="#ffb000", error="#ff5f56", dark=not light,
                     variables={"block-cursor-foreground": bg, "block-cursor-background": fg,
                                "input-selection-background": f"{fg} 35%", "footer-key-foreground": hi,
                                "footer-description-foreground": dim, "border": dim, "border-blurred": dim})

    themes = [theme("ac-" + n.replace(" ", "-"), fg, bg) for n, fg, bg in COLOUR_PRESETS]
    custom = os.environ.get("ANYTHING_COLOURS", "")  # e.g. "#ffcc00,#101010" (text,background)
    if re.fullmatch(r"#[0-9a-fA-F]{6},#[0-9a-fA-F]{6}", custom):
        themes.insert(0, theme("ac-custom", *custom.lower().split(",")))

    line = "ascii" if ascii_mode else "solid"
    tall = "ascii" if ascii_mode else "tall"
    css = f"""
Screen {{ background: $background; }}
* {{ scrollbar-color: $secondary; scrollbar-background: $background; scrollbar-size-vertical: 1; }}
#top {{ height: 1; color: $secondary; }}
#top .name {{ color: $primary; width: auto; text-style: bold; }}
#top .dim {{ width: 1fr; }}
#logo {{ color: $primary; height: auto; margin: 1 0 1 0; text-style: bold; }}
#tagline {{ color: $secondary; margin: 0 0 1 0; }}
#menubar {{ height: 3; border: {line} $secondary; padding: 0 1; }}
#menubar Label {{ width: auto; color: $secondary; padding: 0 1; margin: 0 3 0 0; }}
#menubar Label.on {{ color: $background; background: $primary; }}
#menubar Label.done {{ color: $primary; }}
.frame {{ border: {line} $secondary; border-title-color: $accent; border-title-style: bold; padding: 0 1;
          height: auto; margin: 0 0 1 0; }}
.frame:focus-within {{ border: {line} $primary; }}
.prompt {{ color: $secondary; width: auto; padding: 1 1 0 0; }}
.dim {{ color: $secondary; }}
.hint {{ color: $secondary; margin: 0 0 0 0; }}
.row {{ height: auto; }}
.row Input {{ width: 1fr; }}
Input {{ background: $background; border: {tall} $secondary; color: $accent; }}
Input:focus {{ border: {tall} $primary; }}
Select {{ width: 1fr; }}
Select > SelectCurrent {{ background: $background; border: {tall} $secondary; }}
Select:focus > SelectCurrent {{ border: {tall} $primary; }}
SelectOverlay {{ background: $background; border: {line} $primary; }}
Button {{ background: $background; color: $primary; border: none; min-width: 10; height: 1; margin: 1 1 0 0;
          text-style: none; }}
Button:hover, Button:focus {{ background: $primary; color: $background; text-style: bold; }}
Button.go {{ width: 100%; height: 3; border: {line} $primary; text-style: bold; margin: 0 0 1 0; }}
Button.go:disabled {{ color: $secondary; border: {line} $secondary; }}
RadioSet {{ background: $background; border: none; height: auto; }}
RadioButton, Checkbox {{ background: $background; }}
DirectoryTree {{ height: 12; background: $background; border: {line} $secondary; }}
DirectoryTree:focus {{ border: {line} $primary; }}
ProgressBar {{ margin: 0 0 1 0; }}
Bar > .bar--bar {{ color: $primary; background: #1a2712; }}
Bar > .bar--complete {{ color: $accent; }}
TabbedContent ContentTabs {{ background: $background; }}
Tab {{ color: $secondary; padding: 0 1; }}
Tab.-active {{ color: $accent; text-style: bold; }}
.result {{ border: {line} $primary; padding: 0 1; height: auto; display: none; }}
.result.show {{ display: block; }}
.result.err {{ border: {line} $error; color: $error; }}
TextArea {{ height: 12; background: $background; border: {line} $secondary; }}
#ed-text {{ height: 1fr; min-height: 10; }}
#db-sql {{ height: 6; }}
DataTable {{ height: auto; max-height: 16; background: $background; }}
OptionList {{ height: auto; max-height: 16; background: $background; border: none; }}
.cols {{ height: auto; }}
.cols > Vertical {{ width: 1fr; height: auto; }}
.cols.stack {{ layout: vertical; }}
#tool-grid {{ grid-size: 4; grid-gutter: 0 1; grid-rows: 3; height: auto; }}
#tool-grid.n3 {{ grid-size: 3; }}
#tool-grid.n2 {{ grid-size: 2; }}
#tool-grid.n1 {{ grid-size: 1; }}
.tool {{ width: 100%; height: 3; border: {line} $secondary; margin: 0; padding: 0 1; content-align: left middle;
         text-wrap: nowrap; text-overflow: ellipsis; }}
.tool:hover, .tool:focus {{ border: {line} $primary; background: $background; color: $accent; }}
#status {{ dock: bottom; height: 1; color: $primary; background: $background; padding: 0 1; }}
HelpScreen {{ align: center middle; background: $background 70%; }}
#help {{ width: 84; max-width: 100%; height: auto; max-height: 90%; border: {line} $primary; background: $background;
         padding: 1 2; }}
"""

    def bars(before: int, after: int, width: int = 26) -> str:
        return A(cli.bars(before, after, width).replace("  ORIGINAL", "ORIGINAL").replace("\n  ", "\n"))

    class HelpScreen(ModalScreen):
        BINDINGS = [Binding("escape,f1,question_mark,q", "dismiss", "close")]

        def compose(self) -> ComposeResult:
            with VerticalScroll(id="help"):
                yield Static(A(f"ANYTHING CONVERTER {VERSION} · TERMINAL · HELP\n\nKEYS\n  tab / shift+tab   next / previous field\n  arrows + enter    choose in lists, folders and tabs\n  ctrl+s            start (on the current tab)\n  ctrl+o            type or paste a path\n  ctrl+t            next colour theme (20 themes; --theme / --colours)\n  f1 or ?           this help          ctrl+q   quit\n  1 to 9, 0         go to tab 1-10 (when not in a text field)\n\nTIPS\n  · drag a file into the terminal window to paste its path\n  · results go next to the original; nothing is ever overwritten\n  · CUE/BIN: choose the .cue, the .bin files in the same folder are included\n  · patch a ROM: choose the ROM and enter the .ips/.ups/.bps file at PATCH>\n  · copy text from the text box with ctrl+c (also works over SSH in most terminals)\n\nOTHER WAYS\n  anything-converter-tui --simple     numbered menus, works in any terminal\n  anything-converter-tui --ascii      ASCII characters only (old consoles)\n  anything-converter-tui --help       commands for scripts, e.g.\n      anything-converter-tui convert *.heic --to jpg\n\nesc = close"), markup=False)

    class Converter(App):
        TITLE = "Anything Converter"
        CSS = css
        BINDINGS = [
            Binding("ctrl+s", "start", "start"),
            Binding("ctrl+o", "focus_path", "path"),
            Binding("ctrl+t", "skin", "colour"),
            Binding("f1", "help", "help"),
            Binding("question_mark", "help", "help", show=False),
            Binding("ctrl+q", "quit", "quit"),
        ] + [Binding(str(i), f"tab({i})", show=False) for i in range(1, 10)] + [Binding("0", "tab(10)", show=False)]
        TABS = ["tab-convert", "tab-tools", "tab-pdf", "tab-social", "tab-arch", "tab-fetch", "tab-check",
                "tab-web", "tab-edit", "tab-db"]

        def __init__(self, start_file: str | None = None):
            super().__init__()
            self.src: Path | None = Path(start_file).expanduser().resolve() if start_file else None
            self.cat = "other"
            self.targets: list[str] = []
            self.preset: str | None = None
            self.cancel = threading.Event()

        # ------------------------------------------------------------ opbouw
        def compose(self) -> ComposeResult:
            with Horizontal(id="top"):
                yield Label("ANYTHING CONVERTER (TM)", classes="name")
                yield Label(A(f"   VER {VERSION} · TERMINAL"), classes="dim")
                yield Label(A("f1 help · ctrl+q quit"), classes="dim", id="keys")
            yield Static(LOGO_ASCII if ascii_mode else LOGO, id="logo")
            yield Label(A("> convert · shrink · enlarge · trim · pdf · ocr · speech · roms · social"),
                        id="tagline")
            with Horizontal(id="menubar"):
                for i, txt in enumerate(("01 FILE", "02 FORMAT", "03 OPTIONS", "04 OUTPUT"), 1):
                    yield Label(txt, id=f"step{i}", classes="on" if i == 1 else "")
            with TabbedContent(initial="tab-convert", id="tabs"):
                with TabPane(E("1 CONVERT"), id="tab-convert"):
                    yield from self.compose_convert()
                with TabPane(E("2 TOOLS"), id="tab-tools"):
                    yield from self.compose_tools()
                with TabPane(E("3 PDF"), id="tab-pdf"):
                    yield from self.compose_pdf()
                with TabPane(E("4 SOCIAL"), id="tab-social"):
                    yield from self.compose_social()
                with TabPane(E("5 ARCHIVE"), id="tab-arch"):
                    yield from self.compose_archive()
                with TabPane(E("6 LINK"), id="tab-fetch"):
                    yield from self.compose_fetch()
                with TabPane(E("7 CHECK"), id="tab-check"):
                    yield from self.compose_check()
                with TabPane(E("8 OCR/WEB"), id="tab-web"):
                    yield from self.compose_web()
                with TabPane(E("9 EDITOR"), id="tab-edit"):
                    yield from self.compose_editor()
                with TabPane(E("0 DATABASE"), id="tab-db"):
                    yield from self.compose_db()
            yield Label("> ready", id="status", markup=False)
            yield Footer()

        def frame(self, title: str, **kw):
            v = Vertical(classes="frame", **kw)
            v.border_title = A(title)
            return v

        def compose_convert(self) -> ComposeResult:
            with VerticalScroll():
                with self.frame("01 · FILE", id="f-file"):
                    with Horizontal(classes="row"):
                        yield Label("PATH>", classes="prompt")
                        yield Input(placeholder=A("type or paste a path (or drag a file here)"), id="path")
                    yield Files(str(self.src.parent if self.src else Path.cwd()), id="tree")
                    yield Label(A("// choose a file with the arrows and enter, or click it"), id="fileinfo",
                                markup=False, classes="dim")
                with Horizontal(classes="cols", id="cols"):
                    with self.frame("02 · FORMAT"):
                        yield Select([], prompt="choose a file first", id="format", allow_blank=True)
                        yield Label("", id="fmt-hint", classes="hint", markup=False)
                        yield Label("OUTPUT FOLDER>", classes="prompt")
                        yield Input(placeholder="(same folder as the file)", id="outdir")
                        yield Checkbox(A("All files of this type in this folder"), id="batch")
                    with self.frame("03 · SIZE", id="f-size"):
                        with RadioSet(id="mode"):
                            yield RadioButton("Quality", value=True, id="m-quality")
                            yield RadioButton("Target size", id="m-target")
                        with RadioSet(id="quality"):
                            yield RadioButton("High", id="q-high")
                            yield RadioButton("Normal", value=True, id="q-medium")
                            yield RadioButton("Low", id="q-low")
                        with Horizontal(classes="row"):
                            yield Label("TARGET>", classes="prompt")
                            yield Input(placeholder="e.g. 8 MB or 500 KB", id="target")
                with self.frame("TRIM · VIDEO", id="f-trim"):
                    with Horizontal(classes="row"):
                        yield Label("START>", classes="prompt")
                        yield Input(placeholder="0:00", id="t-start")
                        yield Label("END>", classes="prompt")
                        yield Input(placeholder="end", id="t-end")
                    with Horizontal(classes="row", id="video-row"):
                        yield Select([(f"{h}p", str(h)) for h in (2160, 1440, 1080, 720, 480, 360)],
                                     prompt="resolution: original", id="height", allow_blank=True)
                        yield Select([(n, v) for v, n in (("iphone", "iPhone"), ("ipad", "iPad"),
                                                          ("android", "Android"), ("ipod", "iPod"),
                                                          ("playstation", "PlayStation"), ("psp", "PSP"),
                                                          ("xbox", "Xbox"), ("nintendo-switch", "Nintendo Switch"),
                                                          ("nintendo-3ds", "Nintendo 3DS"), ("wii", "Wii"),
                                                          ("kindle-fire", "Kindle Fire"), ("blackberry", "BlackBerry"))],
                                     prompt="device: no preference", id="device", allow_blank=True)
                    with Horizontal(classes="row", id="codec-row"):
                        yield Select([(n, v) for v, n in (("h264", "H.264"), ("h265", "H.265/HEVC"), ("av1", "AV1"),
                                                          ("vp9", "VP9"), ("prores", "ProRes"), ("mpeg4", "MPEG-4"),
                                                          ("copy", "copy (no re-encode)"))],
                                     prompt="video codec: auto", id="vcodec", allow_blank=True)
                        yield Select([(f, f) for f in ("23.976", "24", "25", "29.97", "30", "50", "60")],
                                     prompt="fps: original", id="fps", allow_blank=True)
                    with Horizontal(classes="row", id="audio-row"):
                        yield Select([(n, v) for v, n in (("aac", "AAC"), ("mp3", "MP3"), ("opus", "Opus"),
                                                          ("flac", "FLAC"), ("ac3", "AC-3"), ("pcm", "PCM"),
                                                          ("copy", "copy"))],
                                     prompt="audio codec: auto", id="acodec", allow_blank=True)
                        yield Select([(f"{k} kbps", k) for k in ("96", "128", "160", "192", "256", "320")],
                                     prompt="audio bitrate: auto", id="abitrate", allow_blank=True)
                    with Horizontal(classes="row"):
                        yield Select([("44.1 kHz", "44100"), ("48 kHz", "48000"), ("22.05 kHz", "22050")],
                                     prompt="sample rate: original", id="srate", allow_blank=True)
                        yield Select([("mono", "mono"), ("stereo", "stereo"), ("5.1", "5.1")],
                                     prompt="channels: original", id="channels", allow_blank=True)
                    with Horizontal(classes="row"):
                        yield Label("TITLE>", classes="prompt")
                        yield Input(placeholder="keep", id="meta-title")
                    yield Checkbox("Remove audio", id="noaudio")
                    yield Checkbox("Remove all metadata (privacy)", id="nometa")
                with self.frame("SPEECH TO TEXT", id="f-speech"):
                    with Horizontal(classes="row"):
                        yield Select([(n, v) for v, n in (("auto", "language: automatic"), ("nl", "Dutch"),
                                                          ("en", "English"), ("de", "German"), ("fr", "French"),
                                                          ("es", "Spanish"), ("it", "Italian"), ("pt", "Portuguese"),
                                                          ("ru", "Russian"), ("tr", "Turkish"), ("ar", "Arabic"),
                                                          ("hi", "Hindi"), ("zh", "Chinese"), ("ja", "Japanese"))],
                                     value="auto", id="lang", allow_blank=False)
                        yield Select([("fast (base, 150 MB)", "base"), ("accurate (small, 480 MB)", "small"),
                                      ("very accurate (medium, 1.5 GB)", "medium")], value="base", id="model",
                                     allow_blank=False)
                    yield Checkbox("Translate to English", id="translate")
                    yield Label(A("// runs locally on your computer. the model is downloaded the first time."),
                                classes="hint")
                with self.frame("DIMENSIONS", id="f-image"):
                    with Horizontal(classes="row"):
                        yield Label("SCALE %>", classes="prompt")
                        yield Input(placeholder="100", id="scale")
                        yield Label("WIDTH>", classes="prompt")
                        yield Input(placeholder="auto", id="img-w")
                        yield Label("HEIGHT>", classes="prompt")
                        yield Input(placeholder="auto", id="img-h")
                with self.frame("ROM-PATCH", id="f-patch"):
                    with Horizontal(classes="row"):
                        yield Label("PATCH>", classes="prompt")
                        yield Input(placeholder=".ips, .ups or .bps", id="patch")
                yield Button(E("[ > START ]  (ctrl+s)") if ascii_mode else E("[ ▶ START ]  (ctrl+s)"), id="go",
                             classes="go")
                yield ProgressBar(total=100, show_eta=False, id="progress")
                yield Static("", id="result", classes="result", markup=False)
                yield TextArea("", id="text-out", read_only=True)

        def compose_tools(self) -> ComposeResult:
            with VerticalScroll():
                with self.frame("TOOLS · PICK AND GO"):
                    with Grid(id="tool-grid"):
                        for i, (a, b, name, _, _) in enumerate(TOOLS):
                            icon = f"{a}>{b}" if ascii_mode else f"{a}→{b}"
                            yield Button(E(f"{icon:<9} {name}"), id=f"tool-{i}", classes="tool")
                    yield Label(A("// pdf, ocr and speech tools pick the format for you; then you choose the file."), classes="hint")

        def compose_pdf(self) -> ComposeResult:
            with VerticalScroll():
                with self.frame("PDF-WERKBANK"):
                    yield Label(A("FILES> one per line, in order (pdfs and/or photos)"), classes="prompt")
                    yield TextArea("", id="pdf-files")
                    with Horizontal(classes="row"):
                        yield Label("PAGES>", classes="prompt")
                        yield Input(placeholder="e.g. 1-3,5  (empty = all)", id="pdf-pages")
                        yield Select([("90° rechtsom", "90"), ("180°", "180"), ("90° linksom", "270")], value="90",
                                     id="pdf-angle", allow_blank=False)
                    with Horizontal(classes="row"):
                        yield Button(E("[ MERGE ]"), id="pdf-merge")
                        yield Button(E("[ SPLIT ]"), id="pdf-split")
                        yield Button(E("[ ROTATE ]"), id="pdf-rotate")
                        yield Button(E("[ DELETE ]"), id="pdf-delete")
                        yield Button(E("[ COMPRIMEREN ]"), id="pdf-compress")
                    yield Label(A("// split without pages = every page separately (zip). with pages = only those pages as one pdf."), classes="hint")
                yield Static("", id="pdf-result", classes="result", markup=False)

        def compose_social(self) -> ComposeResult:
            opts = [(A(social.label(p[1])), p[1]) for p in social.PRESETS]
            with VerticalScroll():
                with self.frame("SOCIAL MEDIA · EXACT SIZE"):
                    with Horizontal(classes="row"):
                        yield Label("FOTO/VIDEO>", classes="prompt")
                        yield Input(placeholder="path to photo or video", id="so-path")
                    yield Select(opts, value="ig-portrait", id="so-preset", allow_blank=False)
                    with RadioSet(id="so-fit"):
                        yield RadioButton("Fill (crop from the centre)", value=True, id="so-cover")
                        yield RadioButton("Passend (alles zichtbaar, vage rand)", id="so-contain")
                    yield Button(E("[ MAKEN ]"), id="so-go", classes="go")
                    yield Label(A("// panorama carousel: a wide photo in pieces to swipe through on instagram, facebook and threads."), classes="hint")
                yield ProgressBar(total=100, show_eta=False, id="so-progress")
                yield Static("", id="so-result", classes="result", markup=False)

        def compose_archive(self) -> ComposeResult:
            with VerticalScroll():
                with self.frame("VIEW / EXTRACT ARCHIVE"):
                    with Horizontal(classes="row"):
                        yield Label("ARCHIVE>", classes="prompt")
                        yield Input(placeholder=".zip, .7z, .tar.gz, ...", id="ar-path")
                    with Horizontal(classes="row"):
                        yield Button(E("[ BEKIJKEN ]"), id="ar-list")
                        yield Button(E("[ EXTRACT ]"), id="ar-extract")
                with self.frame("PACK"):
                    yield Label(A("PATHS> files or folders, one per line"), classes="prompt")
                    yield TextArea("", id="ar-files")
                    with Horizontal(classes="row"):
                        yield Select([(x, x) for x in ("zip", "7z", "tar.gz", "tar.xz", "tar.bz2", "tar")],
                                     value="zip", id="ar-fmt", allow_blank=False)
                        yield Button(E("[ PACK ]"), id="ar-pack")
                yield Static("", id="ar-result", classes="result", markup=False)

        def compose_fetch(self) -> ComposeResult:
            with VerticalScroll():
                with self.frame("LINK · MAGNET · .TORRENT"):
                    with Horizontal(classes="row"):
                        yield Label("LINK>", classes="prompt")
                        yield Input(placeholder=A("https://www.youtube.com/watch?v=…  or  magnet:?…  or .torrent"),
                                    id="url")
                    with Horizontal(classes="row"):
                        yield Checkbox("Audio only", id="audio")
                        yield Checkbox("Check for viruses", value=True, id="scan")
                    with Horizontal(classes="row"):
                        yield Label("SAVE TO>", classes="prompt")
                        yield Input(value=str(Path.home() / "Downloads"), id="dl-dir")
                    with Horizontal(classes="row"):
                        yield Button(E("[ DOWNLOAD ]"), id="fetch")
                        yield Button(E("[ STOP ]"), id="stop")
                    yield ProgressBar(total=100, show_eta=False, id="f-progress")
                    yield Static(A("// only for your own files, free licences or with the creator's permission."),
                                 id="f-result", markup=False, classes="dim")

        def compose_check(self) -> ComposeResult:
            with VerticalScroll():
                with self.frame("VIRUSSCAN & CHECKSUM"):
                    with Horizontal(classes="row"):
                        yield Label("PATH>", classes="prompt")
                        yield Input(placeholder="file or folder", id="scan-path")
                    with Horizontal(classes="row"):
                        yield Label("HMAC>", classes="prompt")
                        yield Input(placeholder="key (optional, checksum only)", id="hmac")
                    with Horizontal(classes="row"):
                        yield Button(E("[ VIRUS SCAN ]"), id="scan-go")
                        yield Button(E("[ CHECKSUM ]"), id="hash-go")
                    yield Static("", id="scan-result", markup=False)
                with self.frame("VIRUSTOTAL (OPTIONEEL)"):
                    with Horizontal(classes="row"):
                        yield Label("KEY>", classes="prompt")
                        yield Input(password=True, placeholder="free api key from virustotal.com", id="vt")
                        yield Button(E("[ SAVE ]"), id="vt-save")
                    yield Label("", id="scanner-info", markup=False, classes="dim")

        def compose_web(self) -> ComposeResult:
            with VerticalScroll():
                with self.frame("RECOGNISE TEXT (OCR)"):
                    with Horizontal(classes="row"):
                        yield Label("FILE>", classes="prompt")
                        yield Input(placeholder="image or scanned pdf", id="ocr-path")
                    with Horizontal(classes="row"):
                        yield Button(E("[ RECOGNISE ]"), id="ocr-go")
                        yield Button(E("[ SCREENSHOT ]"), id="ocr-screen")
                        yield Button(E("[ COPY ]"), id="ocr-copy")
                    yield TextArea("", id="ocr-out", read_only=True)
                with self.frame("SAVE WEBSITE"):
                    with Horizontal(classes="row"):
                        yield Label("URL>", classes="prompt")
                        yield Input(placeholder="https://example.com", id="web-url")
                        yield Select([(".pdf", "pdf"), (".png", "png"), (".jpg", "jpg")], value="pdf", id="web-fmt",
                                     allow_blank=False)
                        yield Button(E("[ SAVE ]"), id="web-go")
                    yield Static("", id="web-result", markup=False, classes="dim")

        def compose_editor(self) -> ComposeResult:
            with Vertical():
                with self.frame("TEXT EDITOR"):
                    with Horizontal(classes="row"):
                        yield Label("FILE>", classes="prompt")
                        yield Input(placeholder="path to a text file (or a new name)", id="ed-path")
                        yield Button(E("[ OPENEN ]"), id="ed-open")
                        yield Button(E("[ VALIDATE ]"), id="ed-check")
                        yield Button(E("[ SAVE ]"), id="ed-save")
                    yield Label(A("// ctrl+s = save. the first save keeps a copy (.bak) of the original."), id="ed-msg", classes="hint", markup=False)
                yield TextArea("", id="ed-text", show_line_numbers=True, tab_behavior="indent")

        def compose_db(self) -> ComposeResult:
            with VerticalScroll():
                with self.frame("DATABASE (SQLITE, .SQL, CSV, EXCEL)"):
                    with Horizontal(classes="row"):
                        yield Label("FILE>", classes="prompt")
                        yield Input(placeholder="path to .sqlite, .db, .sql, .csv or .xlsx", id="db-path")
                        yield Button(E("[ OPENEN ]"), id="db-open")
                        yield Button(E("[ NEW ]"), id="db-new")
                    yield Label(A("// you are working on a copy; export to keep your changes."), id="db-msg",
                                classes="hint", markup=False)
                with Horizontal(classes="cols", id="db-cols"):
                    with self.frame("TABLES"):
                        yield OptionList(id="db-tables")
                    with self.frame("CONTENTS"):
                        yield DataTable(id="db-rows", zebra_stripes=True)
                with self.frame("SQL"):
                    yield TextArea("", id="db-sql")
                    with Horizontal(classes="row"):
                        yield Button(E("[ > UITVOEREN ]") if ascii_mode else E("[ ▶ RUN ]"), id="db-run")
                        yield Select([("database (.sqlite)", "sqlite"), ("sql-dump", "sql"), ("excel", "xlsx"),
                                      ("json", "json"), ("csv", "csv"), ("result as csv", "q-csv"),
                                      ("result as excel", "q-xlsx")], value="sqlite", id="db-fmt", allow_blank=False)
                        yield Button(E("[ EXPORT ]"), id="db-export")
                    yield DataTable(id="db-result", zebra_stripes=True)

        def on_mount(self) -> None:
            for th in themes:
                self.register_theme(th)
            try:
                skin = user_settings.load().get("tui_skin", "ac-green-phosphor")
            except Exception:  # noqa: BLE001
                skin = "ac-green-phosphor"
            wanted = os.environ.get("ANYTHING_THEME", "")
            if wanted:
                skin = "ac-" + wanted.lower().replace(" ", "-").removeprefix("ac-")
            if any(x.name == "ac-custom" for x in themes) and not wanted:
                skin = "ac-custom"
            self.theme = skin if skin in [x.name for x in themes] else "ac-green-phosphor"
            for wid in ("#progress", "#f-progress", "#so-progress", "#text-out"):
                self.query_one(wid).display = False
            self.show_options(None, None)
            eng = virus.available_engine()
            self.query_one("#scanner-info", Label).update(A(
                f"// scanner on this computer: {eng}" if eng else
                "// no scanner found. windows: defender is built in. mac/linux: install clamav."))
            self.relayout(self.size.width)
            if self.src:
                self.choose(self.src)

        def on_resize(self, event) -> None:
            self.relayout(event.size.width)

        def relayout(self, width: int) -> None:
            logo = self.query_one("#logo", Static)
            tall = self.size.height >= 56  # groot logo alleen als er ruimte over is
            if ascii_mode:
                logo.update(LOGO_ASCII if width >= 84 and self.size.height >= 40 else "ANYTHING CONVERTER")
            else:
                logo.update(LOGO if width >= 82 and tall else LOGO_SMALL if width >= len(LOGO_SMALL.splitlines()[0]) + 2 else "ANYTHING CONVERTER")
            h = self.size.height
            logo.display = h >= 30
            self.query_one("#tagline").display = h >= 34
            self.query_one("#menubar").display = h >= 30
            self.query_one("#tree").styles.height = max(5, min(12, h - 20))
            self.query_one("#cols").set_class(width < 96, "stack")
            self.query_one("#keys").display = width >= 70
            grid = self.query_one("#tool-grid")
            for n in ("n1", "n2", "n3"):
                grid.remove_class(n)
            if width < 60:
                grid.add_class("n1")
            elif width < 100:
                grid.add_class("n2")
            elif width < 150:
                grid.add_class("n3")

        # ------------------------------------------------------------ hulpjes
        def status(self, msg: str) -> None:
            self.query_one("#status", Label).update(A("> " + msg))

        def step(self, n: int) -> None:
            for i in range(1, 5):
                lbl = self.query_one(f"#step{i}", Label)
                lbl.set_class(i == n or (n == 2 and i == 3), "on")
                lbl.set_class(i < n, "done")

        def result(self, wid: str, text: str, err: bool = False) -> None:
            res = self.query_one(wid, Static)
            res.set_classes("result show err" if err else "result show")
            res.update(A(text))

        def action_skin(self) -> None:
            names = [x.name for x in themes]
            self.theme = names[(names.index(self.theme) + 1) % len(names)] if self.theme in names else names[0]
            try:
                s = user_settings.load()
                s["tui_skin"] = self.theme
                user_settings.save(s)
            except Exception:  # noqa: BLE001
                pass

        def action_help(self) -> None:
            self.push_screen(HelpScreen())

        def action_tab(self, n: int) -> None:
            if isinstance(self.focused, (Input, TextArea)):
                return
            self.query_one("#tabs", TabbedContent).active = self.TABS[n - 1]

        def action_focus_path(self) -> None:
            self.query_one("#tabs", TabbedContent).active = "tab-convert"
            self.query_one("#path", Input).focus()

        @staticmethod
        def clean(raw: str) -> str:
            """Pad uit invoer: aanhalingstekens en '\\ '-escapes van slepen verwijderen."""
            raw = raw.strip().strip('"').strip("'")
            return raw.replace("\\ ", " ") if os.sep == "/" else raw

        def paths(self, text: str) -> list[Path]:
            return [Path(self.clean(x)).expanduser() for x in text.splitlines() if x.strip()]

        # ------------------------------------------------------------ bestand kiezen
        @on(DirectoryTree.FileSelected, "#tree")
        def tree_pick(self, event) -> None:
            self.choose(Path(event.path))

        @on(Input.Submitted, "#path")
        def path_typed(self, event) -> None:
            p = Path(self.clean(event.value)).expanduser()
            if p.is_dir():
                self.query_one("#tree", DirectoryTree).path = p
            elif p.is_file():
                self.choose(p.resolve())
            else:
                self.status("does not exist: " + event.value)

        def choose(self, path: Path) -> None:
            if not path.is_file():
                return
            from converter.detect import media_info
            self.src = path
            patch_raw = self.query_one("#patch", Input).value.strip()
            info = analyse(path, Path(self.clean(patch_raw)).expanduser() if patch_raw else None)
            self.cat, self.targets = info["category"], info["targets"]
            minfo = media_info(path) if self.cat in ("video", "audio", "image") else {}
            meta = [info["label"], human_size(path.stat().st_size)]
            if minfo.get("width"):
                meta.append(f"{minfo['width']}×{minfo['height']}")
            if minfo.get("duration") and self.cat != "image":
                meta.append(f"{int(minfo['duration'] // 60)}:{minfo['duration'] % 60:04.1f}")
            from converter.catalog import describe
            kind = describe(path)
            if kind:
                meta.append(kind)
            if info.get("ext") and info["ext"] != path.suffix.lower().lstrip("."):
                meta.append(f"eigenlijk .{info['ext']}")
            self.query_one("#fileinfo", Label).update(A(f"NAME  {path.name}\nINFO  {' · '.join(meta)}"))
            self.query_one("#path", Input).value = str(path)
            ext = path.suffix.lower().lstrip(".")
            sel = self.query_one("#format", Select)
            sel.set_options([(A(f".{x}  {fmt_label(self.cat, x)}".rstrip() +
                                ("  (same format)" if x == ext else "")), x) for x in self.targets])
            want = self.preset if self.preset in self.targets else (ext if ext in self.targets else self.targets[0])
            self.preset = None
            sel.value = want
            self.show_options(self.cat, want)
            # handig voor de andere tabbladen
            for wid in ("#so-path", "#ar-path", "#scan-path", "#ocr-path", "#ed-path", "#db-path"):
                inp = self.query_one(wid, Input)
                if not inp.value:
                    inp.value = str(path)
            self.step(2)
            self.status(f"geladen: {path.name} [{info['label'].lower()}]")

        @on(Select.Changed, "#format")
        def fmt_changed(self, event) -> None:
            self.show_options(self.cat if self.src else None, event.value if isinstance(event.value, str) else None)

        def show_options(self, cat, fmt) -> None:
            media = cat in ("video", "audio")
            speech = media and fmt in ("txt", "srt", "vtt")
            texty = speech or (cat == "image" and fmt in ("txt", "docx", "rtf", "xlsx", "svg", "wbmp", "exr", "hdr",
                                                          "eps", "tga")) or \
                (cat == "pdf" and fmt not in (None, "pdf", "png", "jpg")) or cat in ("disc", "rom", "ebook") or \
                (cat is not None and cat not in ("video", "audio", "image", "pdf", "document", "spreadsheet",
                                                 "presentation", "archive", "other"))
            self.query_one("#f-size").display = bool(cat) and not texty
            self.query_one("#f-trim").display = media
            self.query_one("#video-row").display = cat == "video" and not speech
            self.query_one("#noaudio").display = cat == "video" and not speech
            self.query_one("#codec-row").display = cat == "video" and not speech and fmt != "gif"
            for wid in ("#audio-row", "#srate", "#meta-title", "#nometa"):
                w = self.query_one(wid)
                (w.parent if wid in ("#srate", "#meta-title") else w).display = media and not speech
            self.query_one("#f-speech").display = speech
            self.query_one("#f-image").display = cat == "image" and not texty
            self.query_one("#f-patch").display = cat in ("rom",)
            hint = {"disc": "// cue/bin: the .bin files in the same folder are included automatically. chd needs chdman.",
                    "rom": "// patch: enter the .ips/.ups/.bps file below and choose .patch.",
                    "ebook": "// mobi/azw3 and more: install calibre (free) and it works automatically."}.get(cat, "")
            if speech:
                hint = "// speech is recognised locally; long recordings take a while."
            self.query_one("#fmt-hint", Label).update(A(hint))

        @on(Input.Submitted, "#patch")
        def patch_typed(self) -> None:
            if self.src:
                self.choose(self.src)

        # ------------------------------------------------------------ gereedschap
        @on(Button.Pressed, ".tool")
        def tool_pressed(self, event) -> None:
            _, _, name, kind, value = TOOLS[int(event.button.id.split("-")[1])]
            tabs = self.query_one("#tabs", TabbedContent)
            if kind == "tab":
                tabs.active = value
            elif kind == "screen":
                tabs.active = "tab-web"
                self.ocr_screen()
            elif kind == "web":
                tabs.active = "tab-web"
                self.query_one("#web-url", Input).focus()
            else:
                self.preset = value
                tabs.active = "tab-convert"
                self.query_one("#path", Input).focus()
                if self.src and value in self.targets:
                    self.query_one("#format", Select).value = value
                    self.preset = None
                self.status(f"{name.lower()}: choose a file (arrows + enter, or paste a path)")

        # ------------------------------------------------------------ converteren
        def action_start(self) -> None:
            tab = self.query_one("#tabs", TabbedContent).active
            if tab == "tab-convert":
                self.start_convert()
            elif tab == "tab-social":
                self.social_go()
            elif tab == "tab-fetch":
                self.fetch_pressed()

        @on(Button.Pressed, "#go")
        def go_pressed(self) -> None:
            self.start_convert()

        def options(self) -> dict:
            opts: dict = {}
            fmt = self.query_one("#format", Select).value
            if isinstance(fmt, str):
                opts["format"] = fmt
            if self.query_one("#f-size").display and self.query_one("#m-target", RadioButton).value:
                raw = self.query_one("#target", Input).value.strip()
                if not raw:
                    raise ConversionError("Enter a target size, for example 8 MB or 500 KB.")
                opts["target_bytes"] = parse_size(raw, "mb")
            else:
                q = self.query_one("#quality", RadioSet).pressed_button
                opts["quality"] = {"q-high": "high", "q-low": "low"}.get(q.id if q else "", "medium")
            if self.cat in ("video", "audio"):
                for key, wid in (("trim_start", "#t-start"), ("trim_end", "#t-end")):
                    v = self.query_one(wid, Input).value.strip()
                    if v:
                        opts[key] = v
                for key, wid in (("height", "#height"), ("device", "#device"), ("vcodec", "#vcodec"),
                                 ("fps", "#fps"), ("acodec", "#acodec"), ("audio_bitrate", "#abitrate"),
                                 ("sample_rate", "#srate"), ("channels", "#channels")):
                    v = self.query_one(wid, Select).value
                    if isinstance(v, str):
                        opts[key] = int(v) if key == "height" else v
                if self.query_one("#meta-title", Input).value.strip():
                    opts["meta_title"] = self.query_one("#meta-title", Input).value.strip()
                if self.query_one("#nometa", Checkbox).value:
                    opts["metadata"] = "strip"
                if self.query_one("#noaudio", Checkbox).value:
                    opts["remove_audio"] = True
                opts["language"] = self.query_one("#lang", Select).value
                opts["speech_model"] = self.query_one("#model", Select).value
                opts["translate"] = self.query_one("#translate", Checkbox).value
            if self.cat == "image":
                for key, wid in (("scale_percent", "#scale"), ("width", "#img-w"), ("height", "#img-h")):
                    v = self.query_one(wid, Input).value.strip()
                    if v:
                        opts[key] = v
            return opts

        def start_convert(self) -> None:
            if not self.src:
                self.result("#result", "!! ERROR\nChoose a file first.", True)
                return
            try:
                opts = self.options()
            except ConversionError as exc:
                self.result("#result", f"!! ERROR\n{exc}", True)
                return
            patch_raw = self.query_one("#patch", Input).value.strip()
            patch = Path(self.clean(patch_raw)).expanduser() if patch_raw and self.cat == "rom" else None
            out_raw = self.query_one("#outdir", Input).value.strip()
            out_dir = Path(self.clean(out_raw)).expanduser() if out_raw else None
            files = [self.src]
            if self.query_one("#batch", Checkbox).value:
                from converter.detect import detect
                files = sorted(p for p in self.src.parent.iterdir() if p.is_file() and not p.name.startswith(".")
                               and detect(p) == self.cat)
            self.query_one("#go", Button).disabled = True
            self.query_one("#progress", ProgressBar).display = True
            self.query_one("#result").set_classes("result")
            self.query_one("#text-out").display = False
            self.step(4)
            self.cancel.clear()
            self.convert_worker(files, out_dir, opts, patch)

        @work(thread=True, exclusive=True)
        def convert_worker(self, files: list[Path], out_dir, opts: dict, patch) -> None:
            bar = self.query_one("#progress", ProgressBar)
            done_lines, errors, last = [], 0, None
            for k, src in enumerate(files):
                def progress(f: float, msg: str, k=k) -> None:
                    total = (k + f) / len(files)
                    self.call_from_thread(bar.update, progress=round(total * 100, 1))
                    prefix = f"[{k + 1}/{len(files)}] " if len(files) > 1 else ""
                    self.call_from_thread(self.status, f"{prefix}{msg.lower()} {round(f * 100)}%")
                try:
                    dst = cli.convert_file(src, out_dir, dict(opts), progress, patch)
                    last = (src, dst)
                    done_lines.append(f"✓ {src.name} → {dst.name} ({human_size(dst.stat().st_size)})")
                except ConversionError as exc:
                    errors += 1
                    done_lines.append(f"!! {src.name}: {exc}")
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    done_lines.append(f"!! {src.name}: something went wrong: {exc}")
            if len(files) == 1 and last:
                src, dst = last
                text = f"STATUS: OK\nFILE       {dst}\n" + bars(src.stat().st_size, dst.stat().st_size)
                self.call_from_thread(self.result, "#result", text, False)
                if dst.suffix.lower() in (".txt", ".srt", ".vtt"):
                    self.call_from_thread(self.show_text, dst.read_text(encoding="utf-8", errors="replace"))
                self.call_from_thread(self.status, f"done: {dst.name} ({human_size(dst.stat().st_size)})")
            elif len(files) == 1:
                self.call_from_thread(self.result, "#result", "!! ERROR\n" + done_lines[0][3:].split(": ", 1)[-1],
                                      True)
            else:
                head = f"STATUS: {len(files) - errors} of {len(files)} succeeded\n"
                self.call_from_thread(self.result, "#result", head + "\n".join(done_lines[-30:]), bool(errors))
                self.call_from_thread(self.status, f"done: {len(files) - errors}/{len(files)} files")
            self.call_from_thread(self.done_convert)

        def show_text(self, text: str) -> None:
            ta = self.query_one("#text-out", TextArea)
            ta.text = text[:200000]
            ta.display = True

        def done_convert(self) -> None:
            self.query_one("#go", Button).disabled = False
            self.query_one("#progress", ProgressBar).display = False
            self.step(2)

        # ------------------------------------------------------------ pdf
        @on(Button.Pressed, "#pdf-merge, #pdf-split, #pdf-rotate, #pdf-delete, #pdf-compress")
        def pdf_action(self, event) -> None:
            files = self.paths(self.query_one("#pdf-files", TextArea).text)
            if not files and self.src:
                files = [self.src]
            missing = [str(p) for p in files if not p.is_file()]
            if not files or missing:
                self.result("#pdf-result", "!! " + ("does not exist: " + ", ".join(missing) if missing else
                                                    "enter one or more files first"), True)
                return
            action = event.button.id.split("-")[1]
            pages = self.query_one("#pdf-pages", Input).value.strip()
            angle = int(self.query_one("#pdf-angle", Select).value)
            self.result("#pdf-result", "> working…")
            self.pdf_worker(action, files, pages, angle)

        @work(thread=True, group="pdf")
        def pdf_worker(self, action: str, files: list[Path], pages: str, angle: int) -> None:
            from converter import pdftools
            src = files[0]
            try:
                if action == "merge":
                    if len(files) < 2:
                        raise ConversionError("Merge: enter at least two files, one per line.")
                    dst = cli.unique(src.with_name(f"{src.stem}_samengevoegd.pdf"))
                    pdftools.merge(files, dst)
                elif action == "split":
                    dst = pdftools.split(src, src.parent, pages)
                elif action in ("rotate", "delete"):
                    dst = cli.unique(src.with_name(f"{src.stem}_edited.pdf"))
                    pdftools.edit_pages(src, dst, delete=pages if action == "delete" else "",
                                        rotate=(pages or "1-") if action == "rotate" else "", angle=angle)
                else:
                    dst = cli.convert_file(src, None, {"format": "pdf", "quality": "low"})
                text = f"STATUS: OK\nFILE       {dst}\n" + bars(sum(p.stat().st_size for p in files),
                                                               dst.stat().st_size)
                self.call_from_thread(self.result, "#pdf-result", text)
            except (ConversionError, ValueError) as exc:
                self.call_from_thread(self.result, "#pdf-result", f"!! ERROR\n{exc}", True)

        # ------------------------------------------------------------ social
        @on(Button.Pressed, "#so-go")
        def social_go(self) -> None:
            p = Path(self.clean(self.query_one("#so-path", Input).value)).expanduser()
            if not p.is_file():
                self.result("#so-result", "!! choose a photo or video", True)
                return
            pid = self.query_one("#so-preset", Select).value
            fit = "contain" if self.query_one("#so-contain", RadioButton).value else "cover"
            self.query_one("#so-progress").display = True
            self.social_worker(p, pid, fit)

        @work(thread=True, group="social")
        def social_worker(self, p: Path, pid: str, fit: str) -> None:
            from converter.detect import detect
            bar = self.query_one("#so-progress", ProgressBar)

            def progress(f: float, msg: str) -> None:
                self.call_from_thread(bar.update, progress=round(f * 100, 1))
                self.call_from_thread(self.status, f"{msg.lower()} {round(f * 100)}%")

            tmp = Path(tempfile.mkdtemp(prefix="ac-social-"))
            try:
                cat = detect(p)
                if cat == "image":
                    made = social.image(p, tmp, pid, fit, progress)
                elif cat == "video":
                    made = social.video(p, tmp, pid, fit, progress)
                else:
                    raise ConversionError("Choose a photo or video.")
                dst = cli.move_out(made, p.parent)
                self.call_from_thread(self.result, "#so-result",
                                      f"STATUS: OK\nFILE       {dst}\n" + bars(p.stat().st_size, dst.stat().st_size))
            except ConversionError as exc:
                self.call_from_thread(self.result, "#so-result", f"!! ERROR\n{exc}", True)
            except Exception as exc:  # noqa: BLE001
                self.call_from_thread(self.result, "#so-result", f"!! ERROR\n{exc}", True)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
                self.call_from_thread(lambda: setattr(bar, "display", False))

        # ------------------------------------------------------------ archief
        @on(Button.Pressed, "#ar-list, #ar-extract, #ar-pack")
        def archive_action(self, event) -> None:
            import argparse
            import contextlib
            import io
            act = event.button.id.split("-")[1]
            try:
                if act == "pack":
                    paths = self.paths(self.query_one("#ar-files", TextArea).text)
                    if not paths:
                        raise ConversionError("Enter files or folders first, one per line.")
                    ns = argparse.Namespace(actie="pack", paden=paths, uitvoer=None,
                                            formaat=self.query_one("#ar-fmt", Select).value)
                else:
                    p = Path(self.clean(self.query_one("#ar-path", Input).value)).expanduser()
                    if not p.is_file():
                        raise ConversionError("Choose an archive first.")
                    ns = argparse.Namespace(actie="list" if act == "list" else "extract", paden=[p], uitvoer=None,
                                            formaat="zip")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    cli.cmd_archive(ns)
                self.result("#ar-result", buf.getvalue().rstrip())
            except Exception as exc:  # noqa: BLE001
                self.result("#ar-result", f"!! ERROR\n{exc}", True)

        # ------------------------------------------------------------ link & torrent
        @on(Button.Pressed, "#fetch")
        def fetch_pressed(self) -> None:
            src = self.query_one("#url", Input).value.strip()
            if not src:
                return
            self.cancel.clear()
            self.query_one("#fetch", Button).disabled = True
            self.query_one("#f-progress", ProgressBar).display = True
            self.fetch_worker(src, Path(self.clean(self.query_one("#dl-dir", Input).value)).expanduser(),
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
                self.call_from_thread(out.update, A("> " + msg.lower()))

            v = None
            try:
                dl_dir.mkdir(parents=True, exist_ok=True)
                if src.lower().startswith("magnet:?") or src.lower().endswith(".torrent"):
                    source = Path(self.clean(src)).expanduser().read_bytes() if src.lower().endswith(".torrent") \
                        else src
                    res = torrent.download(source, dl_dir, progress, cancelled=self.cancel.is_set)
                    target = dl_dir / res["files"][0]["path"] if len(res["files"]) == 1 else dl_dir / res["name"]
                    lines = [f"TORRENT DONE: {res['name']} · {len(res['files'])} files"]
                    for i, fl in enumerate(res["files"][:40]):
                        lines.append(f"{'└─' if i == len(res['files']) - 1 else '├─'} {fl['path']}  "
                                     f"{human_size(fl['size'])}")
                else:
                    target = fetch.download(src, dl_dir, audio, progress)
                    lines = [f"DOWNLOADED: {target}"]
                if scan:
                    progress(0.995, "checking for viruses")
                    v = virus.check(target, user_settings.load().get("vt_key"))
                    lines.append(cli.virus_line(v))
                    if v["status"] == "infected":
                        lines.append("!! do not open. delete this file.")
                self.call_from_thread(out.update, A("\n".join(lines)))
                if target.is_file() and not (v and v["status"] == "infected"):
                    self.call_from_thread(self.choose, target)
            except ConversionError as exc:
                self.call_from_thread(out.update, A(f"!! {exc}"))
            except Exception as exc:  # noqa: BLE001
                self.call_from_thread(out.update, A(f"!! something went wrong: {exc}"))
            finally:
                self.call_from_thread(lambda: setattr(self.query_one("#fetch", Button), "disabled", False))
                self.call_from_thread(lambda: setattr(bar, "display", False))

        # ------------------------------------------------------------ controle
        @on(Button.Pressed, "#scan-go")
        @on(Input.Submitted, "#scan-path")
        def scan_pressed(self) -> None:
            p = Path(self.clean(self.query_one("#scan-path", Input).value)).expanduser()
            out = self.query_one("#scan-result", Static)
            if not p.exists():
                out.update("!! does not exist")
                return
            out.update("> scannen…" if not ascii_mode else "> scannen...")
            self.scan_worker(p)

        @work(thread=True, group="scan")
        def scan_worker(self, p: Path) -> None:
            v = virus.check(p, user_settings.load().get("vt_key"))
            lines = [cli.virus_line(v)] + [f"sha-256 {f['sha256']}  {f['name']}\n        {f['virustotal']}"
                                           for f in v["files"][:5]]
            self.call_from_thread(self.query_one("#scan-result", Static).update, A("\n".join(lines)))

        @on(Button.Pressed, "#hash-go")
        def hash_pressed(self) -> None:
            p = Path(self.clean(self.query_one("#scan-path", Input).value)).expanduser()
            if not p.is_file():
                self.query_one("#scan-result", Static).update("!! choose a file")
                return
            self.hash_worker(p, self.query_one("#hmac", Input).value.strip() or None)

        @work(thread=True, group="scan")
        def hash_worker(self, p: Path, key) -> None:
            from converter.hashes import compute
            hs = compute(p, key)
            w = max(map(len, hs))
            text = (f"{p.name}{' · HMAC' if key else ''}\n" +
                    "\n".join(f"{k:<{w}}  {v}" for k, v in hs.items()))
            self.call_from_thread(self.query_one("#scan-result", Static).update, A(text))

        @on(Button.Pressed, "#vt-save")
        def vt_save(self) -> None:
            key = self.query_one("#vt", Input).value.strip()
            if key and (len(key) != 64 or any(c not in "0123456789abcdefABCDEF" for c in key)):
                self.query_one("#scanner-info", Label).update("!! a virustotal key has 64 characters (0-9, a-f)")
                return
            s = user_settings.load()
            s["vt_key"] = key
            user_settings.save(s)
            self.query_one("#vt", Input).value = ""
            self.query_one("#scanner-info", Label).update(A("// key saved ✓" if key else
                                                            "// key removed"))

        # ------------------------------------------------------------ ocr & web
        @on(Button.Pressed, "#ocr-go")
        @on(Input.Submitted, "#ocr-path")
        def ocr_go(self) -> None:
            p = Path(self.clean(self.query_one("#ocr-path", Input).value)).expanduser()
            if not p.is_file():
                self.status("choose an image or pdf")
                return
            self.query_one("#ocr-out", TextArea).text = "recognising text…" if not ascii_mode else "working..."
            self.ocr_worker(p, False)

        @on(Button.Pressed, "#ocr-screen")
        def ocr_screen(self) -> None:
            self.query_one("#ocr-out", TextArea).text = "select an area of your screen…" if not ascii_mode else \
                "select an area of your screen..."
            self.ocr_worker(None, True)

        @work(thread=True, group="ocr")
        def ocr_worker(self, p, screen: bool) -> None:
            from converter import ocr
            try:
                path = ocr.capture_screen() if screen else p
                text = ocr.searchable_pdf_text(path) if path.suffix.lower() == ".pdf" else ocr.image(path)
                text = text or "(no text found)"
            except ConversionError as exc:
                text = f"!! {exc}"
            except Exception as exc:  # noqa: BLE001
                text = f"!! {exc}"
            self.call_from_thread(setattr, self.query_one("#ocr-out", TextArea), "text", text)

        @on(Button.Pressed, "#ocr-copy")
        def ocr_copy(self) -> None:
            self.copy_to_clipboard(self.query_one("#ocr-out", TextArea).text)  # OSC 52: werkt ook via SSH
            self.status("text copied to the clipboard")

        @on(Button.Pressed, "#web-go")
        @on(Input.Submitted, "#web-url")
        def web_go(self) -> None:
            url = self.query_one("#web-url", Input).value.strip()
            if url:
                self.query_one("#web-result", Static).update("> website laden...")
                self.web_worker(url, self.query_one("#web-fmt", Select).value)

        @work(thread=True, group="web")
        def web_worker(self, url: str, fmt: str) -> None:
            from converter import webshot
            tmp = Path(tempfile.mkdtemp(prefix="ac-web-"))
            try:
                dst = cli.move_out(webshot.capture(url, tmp, fmt), Path.home() / "Downloads"
                                   if (Path.home() / "Downloads").is_dir() else Path.cwd())
                msg = f"OK: {dst}"
            except ConversionError as exc:
                msg = f"!! {exc}"
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            self.call_from_thread(self.query_one("#web-result", Static).update, A(msg))


        # ------------------------------------------------------------ teksteditor
        @on(Button.Pressed, "#ed-open")
        @on(Input.Submitted, "#ed-path")
        def ed_open(self) -> None:
            from converter.textfmt import read_text
            p = Path(self.clean(self.query_one("#ed-path", Input).value)).expanduser()
            ta = self.query_one("#ed-text", TextArea)
            msg = self.query_one("#ed-msg", Label)
            if p.is_dir() or not str(p).strip():
                msg.update("!! enter a file")
                return
            if p.exists() and p.stat().st_size > 5 * 1024 * 1024:
                msg.update("!! too large to edit here (max. 5 MB)")
                return
            ta.text = read_text(p) if p.exists() else ""
            self.ed_file = p
            msg.update(A(f"// {p.name}: {ta.document.line_count} regels" + ("" if p.exists() else " (new file)")))
            ta.focus()

        @on(Button.Pressed, "#ed-check")
        def ed_check(self) -> None:
            from converter.dbtool import validate
            p = getattr(self, "ed_file", None)
            err = validate(self.query_one("#ed-text", TextArea).text, p.suffix.lower().lstrip(".") if p else "")
            self.query_one("#ed-msg", Label).update(A("// no errors found ✓" if not err else f"!! {err}"))

        @on(Button.Pressed, "#ed-save")
        def ed_save(self) -> None:
            from converter.dbtool import validate
            p = getattr(self, "ed_file", None)
            msg = self.query_one("#ed-msg", Label)
            if not p:
                msg.update("!! open a file first (or type a new name and press open)")
                return
            text = self.query_one("#ed-text", TextArea).text
            try:
                bak = p.with_name(p.name + ".bak")
                if p.exists() and not bak.exists():
                    shutil.copy2(p, bak)
                p.write_text(text, encoding="utf-8", newline="")
            except OSError as exc:
                msg.update(f"!! saving failed: {exc}")
                return
            err = validate(text, p.suffix.lower().lstrip("."))
            msg.update(A(f"// saved ✓ {p}" + (f" — note: {err}" if err else "")))

        def on_key(self, event) -> None:
            if event.key == "ctrl+s" and self.query_one("#tabs", TabbedContent).active == "tab-edit":
                event.prevent_default()
                event.stop()
                self.ed_save()

        # ------------------------------------------------------------ databasetester
        def db_load(self, db: Path) -> None:
            from converter import dbtool
            self.db_file = db
            tables = dbtool.overview(db)
            ol = self.query_one("#db-tables", OptionList)
            ol.clear_options()
            for t in tables:
                ol.add_option(A(f"{'▦' if t['soort'] == 'tabel' else '◇'} {t['naam']} ({t['rijen']})"))
            self.db_tables = [t["naam"] for t in tables]
            if tables:
                self.db_show(tables[0]["naam"])
                sql = self.query_one("#db-sql", TextArea)
                if not sql.text.strip():
                    sql.text = f'SELECT * FROM "{tables[0]["naam"]}" LIMIT 50;'

        def db_fill(self, wid: str, cols, rows) -> None:
            dt = self.query_one(wid, DataTable)
            dt.clear(columns=True)
            if cols:
                dt.add_columns(*[str(c) for c in cols])
                for r in rows:
                    dt.add_row(*["NULL" if v is None else str(v)[:200] for v in r])

        def db_show(self, name: str) -> None:
            from converter import dbtool
            res = dbtool.rows(self.db_file, name)
            self.db_fill("#db-rows", res["kolommen"], res["rijen"])
            self.query_one("#db-msg", Label).update(A(f"// {name}: {res['totaal']} rows"
                                                      + (" (eerste 200 getoond)" if res["totaal"] > 200 else "")))

        @on(Button.Pressed, "#db-open")
        @on(Input.Submitted, "#db-path")
        def db_open(self) -> None:
            from converter import dbtool
            p = Path(self.clean(self.query_one("#db-path", Input).value)).expanduser()
            msg = self.query_one("#db-msg", Label)
            if not p.is_file():
                msg.update("!! file not found")
                return
            work = Path(tempfile.mkdtemp(prefix="ac-db-"))
            try:
                self.db_source = p
                self.db_load(dbtool.prepare(p, work))
            except ConversionError as exc:
                msg.update(A(f"!! {exc}"))

        @on(Button.Pressed, "#db-new")
        def db_new(self) -> None:
            from converter import dbtool
            work = Path(tempfile.mkdtemp(prefix="ac-db-"))
            self.db_source = Path.cwd() / "nieuwe-database.sqlite"
            self.db_load(dbtool.prepare(None, work))
            self.query_one("#db-sql", TextArea).text = (
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT);\n"
                "INSERT INTO customers (name, city) VALUES ('Anna', 'Utrecht'), ('Bo', 'Ghent');\nSELECT * FROM customers;")
            self.query_one("#db-msg", Label).update(A("// new empty database. press run to execute the example."))

        @on(Button.Pressed, "#db-run")
        def db_run(self) -> None:
            from converter import dbtool
            msg = self.query_one("#db-msg", Label)
            if not getattr(self, "db_file", None):
                msg.update("!! open a database first (or choose new)")
                return
            try:
                res = dbtool.query(self.db_file, self.query_one("#db-sql", TextArea).text)
            except ConversionError as exc:
                msg.update(A(f"!! {exc}"))
                self.db_fill("#db-result", [], [])
                return
            self.db_fill("#db-result", res["kolommen"], res["rijen"])
            msg.update(A(f"// {len(res['rijen'])}{'+' if res['meer'] else ''} rows" if res["kolommen"] else
                         f"// done ✓ {res['opdrachten']} statement(s), {res['gewijzigd']} row(s) changed"))
            keep = self.query_one("#db-sql", TextArea).text
            self.db_load(self.db_file)
            self.query_one("#db-sql", TextArea).text = keep

        @on(Button.Pressed, "#db-export")
        def db_export(self) -> None:
            from converter import dbtool
            msg = self.query_one("#db-msg", Label)
            if not getattr(self, "db_file", None):
                msg.update("!! open a database first")
                return
            fmt = self.query_one("#db-fmt", Select).value
            sql = self.query_one("#db-sql", TextArea).text if fmt.startswith("q-") else None
            try:
                tmp = Path(tempfile.mkdtemp(prefix="ac-dbx-"))
                made = dbtool.export(self.db_file, fmt.replace("q-", ""), tmp, self.db_source.name, sql)
                dst = cli.move_out(made, self.db_source.parent)
                msg.update(A(f"// saved ✓ {dst}"))
            except (ConversionError, OSError) as exc:
                msg.update(A(f"!! {exc}"))


        @on(OptionList.OptionSelected, "#db-tables")
        def db_table_pick(self, event) -> None:
            self.db_show(self.db_tables[event.option_index])

    return Converter


def terminal_capable() -> tuple[bool, str]:
    """Kan deze terminal het volledige scherm aan? Zo niet: waarom."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False, "not an interactive terminal (pipe or redirect)"
    term = os.environ.get("TERM", "")
    if os.name != "nt" and term in ("dumb", "unknown", "emacs") or os.environ.get("INSIDE_EMACS"):
        return False, f"terminal type '{term or 'emacs'}' cannot do full screen"
    cols, rows = shutil.get_terminal_size((80, 24))
    if cols < 40 or rows < 12:
        return False, f"window too small ({cols}x{rows})"
    return True, ""


def main(argv: list[str] | None = None) -> int:
    args = cli.parse(sys.argv[1:] if argv is None else argv)
    if args.version:
        print(f"Anything Converter {VERSION} (terminal)")
        return 0
    # meegeleverde programma's (ffmpeg, deno) in de desktop-installatie
    here = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    for bindir in (here / "bin", here.parent / "Resources" / "bin"):  # macOS .app: ook Resources
        if bindir.is_dir():
            os.environ["PATH"] = str(bindir) + os.pathsep + os.environ.get("PATH", "")
            break
    cli.ASCII = args.ascii or cli.wants_ascii()
    if getattr(args, "theme", None):
        os.environ["ANYTHING_THEME"] = args.theme
    if getattr(args, "colours", None):
        os.environ["ANYTHING_COLOURS"] = args.colours
    if args.cmd:
        return cli.run_command(args)
    ok, why = terminal_capable()
    if args.simpel or not ok:
        if not ok and not args.simpel:
            cli.say(f"(simple mode: {why}. full screen cannot be forced; --help for commands)")
        return cli.simple(VERSION)
    try:
        app_cls = build_app(cli.ASCII)
    except Exception as exc:  # noqa: BLE001 - bijv. Textual ontbreekt
        cli.say(f"(full screen not available: {exc}; simple mode)")
        return cli.simple(VERSION)
    app_cls(args.bestand).run()
    return 0


# Voor tests en import: de klasse zonder ASCII-modus
def __getattr__(name):
    if name == "Converter":
        return build_app(False)
    raise AttributeError(name)


def run() -> int:
    try:
        return main()
    except BrokenPipeError:
        # uitvoer naar een programma dat al gestopt is met lezen (bijv. 'head' of 'grep -q'): netjes stoppen
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(run())
