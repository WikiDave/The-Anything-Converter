"""Anything Converter zonder volledig scherm: werkt in elke terminal.

Twee manieren:
- Opdrachten, ook voor scripts:  anything-converter-tui converteer foto.heic --naar jpg
- Eenvoudige modus met genummerde menu's (--simpel): voor terminals zonder kleuren, kaders of muis,
  seriële consoles, oude Windows-consoles, 'dumb' terminals en invoer via een pijp.

Alleen platte tekst (ASCII met --ascii); geen schermbesturing.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .util import ConversionError, human_size, parse_size

ASCII = False
QUALITY = {"hoog": "high", "normaal": "medium", "laag": "low", "high": "high", "medium": "medium", "low": "low"}
REPL = {"█": "#", "░": "-", "▼": "v", "▲": "^", "→": "->", "·": "-", "×": "x", "…": "...", "✓": "OK", "é": "e",
        "ë": "e", "ï": "i", "├": "+", "└": "`", "─": "-", "│": "|", "┌": "+", "┐": "+", "┘": "+", "┤": "|", "▶": ">"}


def t(s: str) -> str:
    """Tekst veilig maken voor de terminal (ASCII-modus of een terminal die geen UTF-8 kan)."""
    if ASCII:
        for a, b in REPL.items():
            s = s.replace(a, b)
        return s.encode("ascii", "replace").decode()
    return s


def say(*parts) -> None:
    text = " ".join(str(p) for p in parts)
    try:
        print(t(text), flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode(), flush=True)


def wants_ascii() -> bool:
    if os.environ.get("ANYTHING_ASCII") == "1":
        return True
    enc = (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "")
    return bool(enc) and "utf" not in enc


class Progress:
    """Voortgangsbalk die werkt met en zonder echte terminal (dan één regel per 10%)."""

    def __init__(self):
        self.tty = sys.stdout.isatty()
        self.last = -1
        self.width = max(10, min(30, shutil.get_terminal_size((80, 24)).columns - 40))

    def __call__(self, frac: float, msg: str) -> None:
        pct = int(max(0, min(1, frac)) * 100)
        if self.tty:
            n = round(pct / 100 * self.width)
            bar = t("[" + "█" * n + "░" * (self.width - n) + "]")
            line = f"\r{bar} {pct:3d}% {t(msg.lower())[:36]:<36}"
            sys.stdout.write(line)
            sys.stdout.flush()
        elif pct // 10 != self.last // 10:
            say(f"  {pct:3d}% {msg.lower()}")
        self.last = pct

    def done(self) -> None:
        if self.tty and self.last >= 0:
            sys.stdout.write("\r" + " " * (self.width + 50) + "\r")
            sys.stdout.flush()


def bars(before: int, after: int, width: int = 24) -> str:
    m = max(before, after, 1)

    def b(n: int) -> str:
        k = max(1, round(n / m * width))
        return "█" * k + "░" * (width - k)

    d = (after - before) / before * 100 if before else 0
    return (f"  ORIGINEEL  {b(before)} {human_size(before)}\n  NIEUW      {b(after)} {human_size(after)}\n"
            f"  VERSCHIL   {'▼' if d <= 0 else '▲'} {abs(d):.1f}% {'kleiner' if d <= 0 else 'groter'}")


def unique(dst: Path) -> Path:
    n = 2
    out = dst
    while out.exists():
        out = dst.with_name(f"{dst.stem}_{n}{dst.suffix}")
        n += 1
    return out


def convert_file(src: Path, out_dir: Path | None, opts: dict, progress=None, patch: Path | None = None) -> Path:
    """Eén bestand omzetten; het resultaat komt naast het origineel (of in out_dir), nooit overschreven."""
    from .formats import analyse
    from .jobs import run_conversion
    src = src.expanduser().resolve()
    if not src.is_file():
        raise ConversionError(f"Bestand niet gevonden: {src}")
    info = analyse(src, patch)
    fmt = opts.get("format")
    if fmt and fmt not in info["targets"]:
        raise ConversionError(f"{src.name} ({info['label'].lower()}) kan niet naar .{fmt}. "
                              f"Mogelijk: {', '.join(info['targets'])}")
    if patch:
        opts = dict(opts, patch=str(patch))
    tmp = Path(tempfile.mkdtemp(prefix="ac-cli-"))
    try:
        made = run_conversion(src, tmp, info["category"], opts, progress)
        target_dir = (out_dir or src.parent).expanduser()
        target_dir.mkdir(parents=True, exist_ok=True)
        dst = unique(target_dir / made.name)
        shutil.move(str(made), dst)
        return dst
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def move_out(made: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = unique(out_dir / made.name)
    shutil.move(str(made), dst)
    return dst


# ============================================================================ opdrachten

def build_parser(with_file: bool = False) -> argparse.ArgumentParser:
    """with_file: zonder opdracht, met een optioneel bestand om in het volledige scherm te openen."""
    ap = argparse.ArgumentParser(
        prog="anything-converter-tui",
        description="Anything Converter in de terminal. Zonder opdracht: volledig scherm (of --simpel).",
        epilog="Voorbeelden:\n"
               "  anything-converter-tui converteer video.mov --naar mp4 --doel 25MB\n"
               "  anything-converter-tui converteer *.heic --naar jpg --uit ~/Foto's\n"
               "  anything-converter-tui converteer rapport.pdf --naar docx\n"
               "  anything-converter-tui converteer interview.mp3 --naar srt --taal nl\n"
               "  anything-converter-tui pdf samenvoegen a.pdf b.pdf -o samen.pdf\n"
               "  anything-converter-tui social vakantie.jpg --formaat ig-pano\n"
               "  anything-converter-tui converteer spel.cue --naar chd\n"
               "  anything-converter-tui --simpel",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="store_true", help="versie tonen")
    ap.add_argument("--simpel", action="store_true", help="eenvoudige modus met menu's (werkt in elke terminal)")
    ap.add_argument("--ascii", action="store_true", help="alleen ASCII-tekens (oude of beperkte terminals)")
    if with_file:
        ap.add_argument("bestand", nargs="?", help="bestand om direct te openen")
        ap.set_defaults(cmd=None)
        ap.epilog = ("Opdrachten (meer uitleg: anything-converter-tui <opdracht> --help):\n"
                     "  converteer, formaten, hash, pdf, archief, social, ocr, web, ophalen, scan\n\n" + ap.epilog)
        return ap
    sub = ap.add_subparsers(dest="cmd", metavar="opdracht")

    c = sub.add_parser("converteer", aliases=["convert"], help="bestanden omzetten")
    c.add_argument("bestanden", nargs="+", type=Path)
    c.add_argument("--naar", "--to", required=True, help="uitvoerformaat, bijv. mp4, jpg, docx, iso")
    c.add_argument("--uit", "--out", type=Path, help="uitvoermap (standaard: naast het bestand)")
    c.add_argument("--kwaliteit", default="normaal", choices=list(QUALITY))
    c.add_argument("--doel", help="doelgrootte, bijv. 8MB of 500KB")
    c.add_argument("--van", help="knippen vanaf (bijv. 0:10)")
    c.add_argument("--tot", help="knippen tot (bijv. 1:30)")
    c.add_argument("--hoogte", type=int, help="videohoogte in pixels, bijv. 720")
    c.add_argument("--zonder-geluid", action="store_true")
    c.add_argument("--apparaat", help="video-preset: iphone, android, psp, xbox, ...")
    c.add_argument("--schaal", type=float, help="afbeelding schalen in procent")
    c.add_argument("--breedte", type=int)
    c.add_argument("--taal", default="auto", help="spraak naar tekst: auto, nl, en, de, ...")
    c.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium"])
    c.add_argument("--vertaal", action="store_true", help="spraak vertalen naar Engels")
    c.add_argument("--patch", type=Path, help="IPS/UPS/BPS-patch voor --naar patch")

    f = sub.add_parser("formaten", aliases=["formats", "info"], help="wat kan dit bestand worden?")
    f.add_argument("bestand", type=Path)

    h = sub.add_parser("hash", aliases=["checksum"], help="checksums (MD5, SHA-256, CRC-32, ...)")
    h.add_argument("bestanden", nargs="+", type=Path)
    h.add_argument("--hmac", help="sleutel voor HMAC")

    p = sub.add_parser("pdf", help="PDF-werkbank")
    p.add_argument("actie", choices=["samenvoegen", "splitsen", "draaien", "verwijderen", "comprimeren"])
    p.add_argument("bestanden", nargs="+", type=Path)
    p.add_argument("-o", "--uitvoer", type=Path)
    p.add_argument("--paginas", default="", help="bijv. 1-3,5")
    p.add_argument("--hoek", type=int, default=90, choices=[90, 180, 270])
    p.add_argument("--doel", help="comprimeren tot bijv. 2MB")

    a = sub.add_parser("archief", aliases=["archive"], help="zip/7z/tar bekijken, uitpakken of maken")
    a.add_argument("actie", choices=["lijst", "uitpakken", "inpakken"])
    a.add_argument("paden", nargs="+", type=Path)
    a.add_argument("-o", "--uitvoer", type=Path)
    a.add_argument("--formaat", default="zip", choices=["zip", "7z", "tar.gz", "tar.xz", "tar.bz2", "tar"])

    s = sub.add_parser("social", help="foto/video op het formaat van een platform")
    s.add_argument("bestand", nargs="?", type=Path)
    s.add_argument("--formaat", help="bijv. ig-story, ig-pano, yt-thumb (zonder: lijst tonen)")
    s.add_argument("--passend", action="store_true", help="niet bijsnijden maar passend maken (vage achtergrond)")
    s.add_argument("--uit", type=Path)

    o = sub.add_parser("ocr", help="tekst herkennen in een afbeelding, scan of schermafbeelding")
    o.add_argument("bestand", nargs="?", type=Path)
    o.add_argument("--scherm", action="store_true", help="een gebied van je scherm kiezen")

    w = sub.add_parser("web", help="website opslaan als pdf/png/jpg")
    w.add_argument("url")
    w.add_argument("--naar", default="pdf", choices=["pdf", "png", "jpg"])
    w.add_argument("--uit", type=Path, default=Path.cwd())

    g = sub.add_parser("ophalen", aliases=["fetch"], help="video via een link, of torrent (magnet / .torrent)")
    g.add_argument("bron")
    g.add_argument("--uit", type=Path, default=Path.home() / "Downloads")
    g.add_argument("--audio", action="store_true", help="alleen geluid")
    g.add_argument("--geen-scan", action="store_true")

    v = sub.add_parser("scan", help="bestand of map controleren op virussen")
    v.add_argument("pad", type=Path)
    return ap


def run_command(args) -> int:
    try:
        return COMMANDS[args.cmd](args)
    except ConversionError as e:
        say("!! FOUT:", e)
        return 1
    except KeyboardInterrupt:
        say("\n!! gestopt")
        return 130


def cmd_convert(a) -> int:
    opts: dict = {"format": a.naar.lower().lstrip("."), "quality": QUALITY[a.kwaliteit]}
    if a.doel:
        opts["target_bytes"] = parse_size(a.doel, "mb")
    for k, v in (("trim_start", a.van), ("trim_end", a.tot), ("height", a.hoogte), ("device", a.apparaat),
                 ("scale_percent", a.schaal), ("width", a.breedte)):
        if v:
            opts[k] = v
    if a.zonder_geluid:
        opts["remove_audio"] = True
    opts.update(language=a.taal, speech_model=a.model, translate=a.vertaal)
    fails = 0
    for src in a.bestanden:
        say(f"> {src.name} -> .{opts['format']}")
        bar = Progress()
        try:
            dst = convert_file(src, a.uit, dict(opts), bar, a.patch)
            bar.done()
            say(f"  OK: {dst}")
            say(bars(src.stat().st_size, dst.stat().st_size))
        except ConversionError as e:
            bar.done()
            say(f"  !! {e}")
            fails += 1
    return 1 if fails else 0


def cmd_formats(a) -> int:
    from .formats import analyse, fmt_label
    info = analyse(a.bestand)
    say(f"{a.bestand.name}: {info['label']}, {human_size(a.bestand.stat().st_size)}")
    for x in info["targets"]:
        lbl = fmt_label(info["category"], x)
        say(f"  .{x:<8} {lbl}")
    return 0


def cmd_hash(a) -> int:
    from .hashes import compute
    for p in a.bestanden:
        say(f"{p.name}{' (HMAC)' if a.hmac else ''}")
        hs = compute(p, a.hmac)
        w = max(map(len, hs))
        for k, v in hs.items():
            say(f"  {k:<{w}}  {v}")
    return 0


def cmd_pdf(a) -> int:
    from . import pdftools
    src = a.bestanden[0]
    if a.actie == "samenvoegen":
        dst = unique(a.uitvoer or src.with_name(f"{src.stem}_samengevoegd.pdf"))
        pdftools.merge(a.bestanden, dst)
    elif a.actie == "splitsen":
        out_dir = a.uitvoer or src.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = pdftools.split(src, out_dir, a.paginas)
    elif a.actie in ("draaien", "verwijderen"):
        dst = unique(a.uitvoer or src.with_name(f"{src.stem}_bewerkt.pdf"))
        pdftools.edit_pages(src, dst, delete=a.paginas if a.actie == "verwijderen" else "",
                            rotate=(a.paginas or "1-") if a.actie == "draaien" else "", angle=a.hoek)
    else:
        opts = {"format": "pdf", "quality": "low" if not a.doel else "medium"}
        if a.doel:
            opts["target_bytes"] = parse_size(a.doel, "mb")
        dst = convert_file(src, a.uitvoer, opts, Progress())
    say(f"OK: {dst} ({human_size(dst.stat().st_size)})")
    return 0


def cmd_archive(a) -> int:
    from .archive import _is_7z, _pack, _safe_extract
    if a.actie == "lijst":
        import tarfile
        import zipfile
        src = a.paden[0]
        if zipfile.is_zipfile(src):
            rows = [(i.filename, i.file_size) for i in zipfile.ZipFile(src).infolist() if not i.is_dir()]
        elif _is_7z(src):
            import py7zr
            with py7zr.SevenZipFile(src) as z:
                rows = [(i.filename, i.uncompressed or 0) for i in z.list() if not i.is_directory]
        elif tarfile.is_tarfile(src):
            with tarfile.open(src) as tf:
                rows = [(m.name, m.size) for m in tf.getmembers() if m.isfile()]
        else:
            raise ConversionError("Dit is geen zip-, 7z- of tar-archief.")
        for name, size in rows:
            say(f"  {human_size(size):>10}  {name}")
        say(f"{len(rows)} bestanden, {human_size(sum(s for _, s in rows))} uitgepakt")
        return 0
    if a.actie == "uitpakken":
        src = a.paden[0]
        dest = a.uitvoer or src.with_name(src.name.split(".")[0])
        dest.mkdir(parents=True, exist_ok=True)
        _safe_extract(src, dest)
        say(f"OK: uitgepakt in {dest}")
        return 0
    first = a.paden[0]
    dst = unique(a.uitvoer or first.with_name(f"{first.stem if first.is_file() else first.name}.{a.formaat}"))
    base = Path(os.path.commonpath([str(p.resolve().parent) for p in a.paden]))
    _pack([p.resolve() for p in a.paden], base, dst, a.formaat, 9)
    say(f"OK: {dst} ({human_size(dst.stat().st_size)})")
    return 0


def cmd_social(a) -> int:
    from . import social
    if not a.formaat or not a.bestand:
        group = None
        for g, pid, name, w, h, _ in social.PRESETS:
            if g != group:
                say(f"{g}")
                group = g
            say(f"  {pid:<14} {name} ({w}x{h})")
        return 0
    from .detect import detect
    cat = detect(a.bestand)
    tmp = Path(tempfile.mkdtemp(prefix="ac-social-"))
    try:
        fit = "contain" if a.passend else "cover"
        if cat == "image":
            made = social.image(a.bestand, tmp, a.formaat, fit, Progress())
        elif cat == "video":
            made = social.video(a.bestand, tmp, a.formaat, fit, Progress())
        else:
            raise ConversionError("Kies een foto of video.")
        dst = move_out(made, a.uit or a.bestand.parent)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    say(f"OK: {dst} ({human_size(dst.stat().st_size)})")
    return 0


def cmd_ocr(a) -> int:
    from . import ocr
    if a.scherm:
        path = ocr.capture_screen()
    elif a.bestand:
        path = a.bestand
    else:
        raise ConversionError("Geef een afbeelding of PDF, of gebruik --scherm.")
    text = ocr.searchable_pdf_text(path) if path.suffix.lower() == ".pdf" else ocr.image(path)
    print(text)
    return 0


def cmd_web(a) -> int:
    from . import webshot
    a.uit.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="ac-web-"))
    try:
        dst = move_out(webshot.capture(a.url, tmp, a.naar, Progress()), a.uit)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    say(f"OK: {dst}")
    return 0


def cmd_fetch(a) -> int:
    from . import fetch, torrent, virus
    from . import settings as user_settings
    a.uit.mkdir(parents=True, exist_ok=True)
    bar = Progress()
    if a.bron.lower().startswith("magnet:?") or a.bron.lower().endswith(".torrent"):
        source = Path(a.bron).expanduser().read_bytes() if a.bron.lower().endswith(".torrent") else a.bron
        res = torrent.download(source, a.uit, bar)
        target = a.uit / res["files"][0]["path"] if len(res["files"]) == 1 else a.uit / res["name"]
    else:
        target = fetch.download(a.bron, a.uit, a.audio, bar)
    bar.done()
    say(f"OK: {target}")
    if not a.geen_scan:
        v = virus.check(target, user_settings.load().get("vt_key"))
        say(virus_line(v))
        return 2 if v["status"] == "infected" else 0
    return 0


def virus_line(v: dict) -> str:
    loc = v["local"]
    vt = next((f["vt"]["detail"] for f in v.get("files", []) if f.get("vt")), None)
    extra = f" - virustotal: {vt}" if vt else ""
    if v["status"] == "infected":
        return f"!! VIRUS GEVONDEN ({loc.get('engine')}): {loc.get('detail')}{extra}"
    if v["status"] == "clean":
        return f"✓ geen virus gevonden ({loc.get('engine')}){extra}"
    return f"? niet zeker: {loc.get('detail')}{extra}"


def cmd_scan(a) -> int:
    from . import virus
    from . import settings as user_settings
    v = virus.check(a.pad, user_settings.load().get("vt_key"))
    say(virus_line(v))
    for f in v["files"][:10]:
        say(f"  sha-256 {f['sha256']}  {f['name']}")
    return 2 if v["status"] == "infected" else 0


def parse(argv: list[str]) -> argparse.Namespace:
    first = next((a for a in argv if not a.startswith("-")), None)
    return build_parser(with_file=first not in COMMANDS).parse_args(argv)


COMMANDS = {"converteer": cmd_convert, "convert": cmd_convert, "formaten": cmd_formats, "formats": cmd_formats,
            "info": cmd_formats, "hash": cmd_hash, "checksum": cmd_hash, "pdf": cmd_pdf, "archief": cmd_archive,
            "archive": cmd_archive, "social": cmd_social, "ocr": cmd_ocr, "web": cmd_web, "ophalen": cmd_fetch,
            "fetch": cmd_fetch, "scan": cmd_scan}


# ============================================================================ eenvoudige modus

def ask(prompt: str, default: str = "") -> str:
    try:
        val = input(t(f"{prompt}{f' [{default}]' if default else ''}> "))
    except EOFError:
        raise SystemExit(0)
    return val.strip().strip('"').strip("'") or default


def choose(title: str, options: list[str], allow_back: bool = True) -> int:
    """Genummerd menu; geeft de index terug, of -1 voor terug."""
    say("")
    say(title)
    for i, o in enumerate(options, 1):
        say(f"  {i:>2}) {o}")
    if allow_back:
        say("   0) terug")
    while True:
        raw = ask("keuze")
        if raw.lower() in ("q", "stop", "exit", "quit"):
            raise SystemExit(0)
        if raw == "0" and allow_back:
            return -1
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        say("  kies een nummer uit de lijst")


def ask_path(prompt: str, must_exist: bool = True) -> Path | None:
    while True:
        raw = ask(prompt + " (leeg = terug)")
        if not raw:
            return None
        p = Path(raw).expanduser()
        if not must_exist or p.exists():
            return p
        say(f"  bestaat niet: {p}")


def simple(version: str) -> int:
    say(f"ANYTHING CONVERTER {version} - eenvoudige modus")
    say("werkt in elke terminal. q = afsluiten. tip: sleep een bestand in dit venster om het pad te plakken.")
    menu = ["bestand converteren", "pdf: samenvoegen / splitsen / pagina's draaien of verwijderen",
            "social media formaat", "tekst herkennen (ocr)", "video-link of torrent ophalen",
            "virusscan of checksum", "archief: bekijken / uitpakken / inpakken", "website opslaan als pdf/png/jpg"]
    while True:
        try:
            k = choose("WAT WIL JE DOEN?", menu + ["afsluiten"], allow_back=False)
            if k == len(menu):
                return 0
            [simple_convert, simple_pdf, simple_social, simple_ocr, simple_fetch, simple_scan, simple_archive,
             simple_web][k]()
        except ConversionError as e:
            say(f"!! {e}")
        except KeyboardInterrupt:
            say("\n(onderbroken)")


def simple_convert() -> None:
    from .formats import analyse, fmt_label
    src = ask_path("bestand")
    if not src:
        return
    patch = None
    info = analyse(src)
    say(f"{src.name}: {info['label']}, {human_size(src.stat().st_size)}")
    if info["category"] == "rom":
        pp = ask("patch (.ips/.ups/.bps) toepassen? pad of leeg")
        if pp:
            patch = Path(pp).expanduser()
            info = analyse(src, patch)
    k = choose("NAAR WELK FORMAAT?", [f".{x}  {fmt_label(info['category'], x)}" for x in info["targets"]])
    if k < 0:
        return
    fmt = info["targets"][k]
    opts: dict = {"format": fmt}
    cat = info["category"]
    if cat in ("video", "audio", "image", "pdf") and fmt not in ("txt", "srt", "vtt", "docx", "rtf", "xlsx"):
        g = choose("GROOTTE", ["kwaliteit hoog", "kwaliteit normaal", "kwaliteit laag", "doelgrootte (bijv. 8 MB)"])
        if g == 3:
            opts["target_bytes"] = parse_size(ask("doelgrootte", "8 MB"), "mb")
        elif g >= 0:
            opts["quality"] = ["high", "medium", "low"][g]
    if cat in ("video", "audio"):
        s, e = ask("knippen vanaf (leeg = begin)"), ask("knippen tot (leeg = einde)")
        if s:
            opts["trim_start"] = s
        if e:
            opts["trim_end"] = e
        if fmt in ("txt", "srt", "vtt"):
            opts["language"] = ask("taal (auto, nl, en, de, fr, ...)", "auto")
            opts["speech_model"] = ask("model (base = snel, small = nauwkeurig)", "base")
    out = ask("uitvoermap (leeg = naast het bestand)")
    bar = Progress()
    dst = convert_file(src, Path(out).expanduser() if out else None, opts, bar, patch)
    bar.done()
    say(f"OK: {dst}")
    say(bars(src.stat().st_size, dst.stat().st_size))


def simple_pdf() -> None:
    k = choose("PDF", ["samenvoegen (pdf's en/of foto's)", "splitsen", "pagina's draaien", "pagina's verwijderen",
                       "comprimeren"])
    if k < 0:
        return
    args = argparse.Namespace(actie=["samenvoegen", "splitsen", "draaien", "verwijderen", "comprimeren"][k],
                              uitvoer=None, paginas="", hoek=90, doel=None, bestanden=[])
    if k == 0:
        say("geef de bestanden in volgorde; leeg = klaar")
        while True:
            p = ask_path(f"bestand {len(args.bestanden) + 1}")
            if not p:
                break
            args.bestanden.append(p)
        if len(args.bestanden) < 2:
            say("  minstens twee bestanden nodig")
            return
    else:
        p = ask_path("pdf")
        if not p:
            return
        args.bestanden = [p]
        if k == 1:
            args.paginas = ask("alleen deze pagina's als één pdf (bijv. 1-3,5; leeg = elke pagina apart)")
        elif k in (2, 3):
            args.paginas = ask("welke pagina's (bijv. 1-3,5)", "1-" if k == 2 else "")
            if k == 2:
                args.hoek = int(ask("hoek (90, 180, 270)", "90"))
        elif k == 4:
            args.doel = ask("doelgrootte (leeg = zo klein mogelijk)") or None
    cmd_pdf(args)


def simple_social() -> None:
    from . import social
    src = ask_path("foto of video")
    if not src:
        return
    groups = list(dict.fromkeys(p[0] for p in social.PRESETS))
    g = choose("PLATFORM", groups)
    if g < 0:
        return
    items = [p for p in social.PRESETS if p[0] == groups[g]]
    k = choose(groups[g].upper(), [f"{p[2]} ({p[3]}x{p[4]})" for p in items])
    if k < 0:
        return
    fit = choose("BIJSNIJDEN?", ["vullen (bijsnijden vanuit het midden)", "passend (alles zichtbaar, vage rand)"])
    cmd_social(argparse.Namespace(bestand=src, formaat=items[k][1], passend=fit == 1, uit=None))


def simple_ocr() -> None:
    k = choose("TEKST HERKENNEN", ["uit een afbeelding of scan (pdf)", "uit een stuk van mijn scherm"])
    if k < 0:
        return
    p = None if k == 1 else ask_path("afbeelding of pdf")
    if k == 0 and not p:
        return
    say("-" * 40)
    cmd_ocr(argparse.Namespace(bestand=p, scherm=k == 1))
    say("-" * 40)


def simple_fetch() -> None:
    src = ask("link, magnet:?... of pad naar .torrent (leeg = terug)")
    if not src:
        return
    audio = ask("alleen geluid? (j/n)", "n").lower().startswith("j")
    out = Path(ask("opslaan in", str(Path.home() / "Downloads"))).expanduser()
    cmd_fetch(argparse.Namespace(bron=src, uit=out, audio=audio, geen_scan=False))


def simple_scan() -> None:
    k = choose("CONTROLEREN", ["virusscan", "checksum (md5, sha-256, crc-32, ...)"])
    if k < 0:
        return
    p = ask_path("bestand of map" if k == 0 else "bestand")
    if not p:
        return
    if k == 0:
        cmd_scan(argparse.Namespace(pad=p))
    else:
        cmd_hash(argparse.Namespace(bestanden=[p], hmac=ask("hmac-sleutel (leeg = geen)") or None))


def simple_archive() -> None:
    k = choose("ARCHIEF", ["inhoud bekijken", "uitpakken", "inpakken (zip, 7z, tar)"])
    if k < 0:
        return
    if k < 2:
        p = ask_path("archief")
        if not p:
            return
        out = None if k == 0 else Path(ask("uitpakken naar", str(p.with_name(p.name.split(".")[0]))))
        cmd_archive(argparse.Namespace(actie=["lijst", "uitpakken"][k], paden=[p], uitvoer=out, formaat="zip"))
        return
    paden = []
    say("bestanden of mappen om in te pakken; leeg = klaar")
    while True:
        p = ask_path(f"pad {len(paden) + 1}")
        if not p:
            break
        paden.append(p)
    if not paden:
        return
    fmt = ["zip", "7z", "tar.gz", "tar.xz"][max(0, choose("FORMAAT", ["zip", "7z", "tar.gz", "tar.xz"]))]
    cmd_archive(argparse.Namespace(actie="inpakken", paden=paden, uitvoer=None, formaat=fmt))


def simple_web() -> None:
    url = ask("websiteadres (leeg = terug)")
    if not url:
        return
    k = choose("OPSLAAN ALS", ["pdf", "png", "jpg"])
    if k < 0:
        return
    cmd_web(argparse.Namespace(url=url, naar=["pdf", "png", "jpg"][k], uit=Path(ask("map", str(Path.cwd())))))

