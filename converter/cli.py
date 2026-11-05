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
QUALITY = {"hoog": "high", "normaal": "medium", "laag": "low", "normal": "medium", "high": "high", "medium": "medium", "low": "low"}
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
    return (f"  ORIGINAL   {b(before)} {human_size(before)}\n  NEW        {b(after)} {human_size(after)}\n  DIFFERENCE {'▼' if d <= 0 else '▲'} {abs(d):.1f}% {'smaller' if d <= 0 else 'larger'}")


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
        raise ConversionError(f"File not found: {src}")
    info = analyse(src, patch)
    fmt = opts.get("format")
    if fmt and fmt not in info["targets"]:
        raise ConversionError(f"{src.name} ({info['label'].lower()}) cannot become .{fmt}. Possible: {', '.join(info['targets'])}")
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

PDF_ACTIONS = {"merge": "merge", "split": "split", "rotate": "rotate", "delete": "delete", "compress": "compress",
               "samenvoegen": "merge", "splitsen": "split", "draaien": "rotate", "verwijderen": "delete",
               "comprimeren": "compress"}
ARCHIVE_ACTIONS = {"list": "list", "extract": "extract", "pack": "pack",
                   "lijst": "list", "uitpakken": "extract", "inpakken": "pack"}


def _action(table: dict):
    def conv(s: str) -> str:
        if s.lower() not in table:
            raise argparse.ArgumentTypeError(f"choose from: {', '.join(sorted(set(table.values())))}")
        return table[s.lower()]
    return conv


def build_parser(with_file: bool = False) -> argparse.ArgumentParser:
    """with_file: no command, with an optional file to open in full screen."""
    ap = argparse.ArgumentParser(
        prog="anything-converter-tui",
        description="Anything Converter in the terminal. Without a command: full screen (or --simple).",
        epilog="Examples:\n"
               "  anything-converter-tui convert video.mov --to mp4 --target 25MB\n"
               "  anything-converter-tui convert *.heic --to jpg --out ~/Pictures\n"
               "  anything-converter-tui convert report.pdf --to docx\n"
               "  anything-converter-tui convert interview.mp3 --to srt --lang en\n"
               "  anything-converter-tui pdf merge a.pdf b.pdf -o together.pdf\n"
               "  anything-converter-tui social holiday.jpg --size ig-pano\n"
               "  anything-converter-tui convert game.cue --to chd\n"
               "  anything-converter-tui --simple\n\n"
               "Dutch command names (converteer, --naar, --simpel, ...) still work.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="store_true", help="show the version")
    ap.add_argument("--simple", "--simpel", dest="simpel", action="store_true",
                    help="simple mode with numbered menus (works in any terminal)")
    ap.add_argument("--ascii", action="store_true", help="ASCII characters only (old or limited terminals)")
    ap.add_argument("--theme", help="colour theme: green-phosphor, amber, cyan, white, matrix, red-alert, pink, "
                                    "purple, ice, gold, dos, c64, solarized, gruvbox, nord, dracula, high-contrast, "
                                    "paper, sepia, green-on-white (ctrl+t switches)")
    ap.add_argument("--colours", "--colors", dest="colours", metavar="TEXT,BACKGROUND",
                    help='your own colours, e.g. "#ffcc00,#101010"')
    ap.add_argument("--ui-lang", "--taal-ui", dest="ui_lang", choices=["en", "nl"],
                    help="language of the terminal texts (default: en; or set ANYTHING_LANG=nl)")
    if with_file:
        ap.add_argument("bestand", nargs="?", metavar="file", help="file to open straight away")
        ap.set_defaults(cmd=None)
        ap.epilog = ("Commands (more help: anything-converter-tui <command> --help):\n"
                     "  convert, formats, hash, pdf, archive, social, ocr, web, fetch, scan, sql, drives\n\n" + ap.epilog)
        return ap
    sub = ap.add_subparsers(dest="cmd", metavar="command")

    c = sub.add_parser("convert", aliases=["converteer"], help="convert files")
    c.add_argument("bestanden", nargs="+", type=Path, metavar="file")
    c.add_argument("--to", "--naar", dest="naar", required=True, help="output format, e.g. mp4, jpg, docx, iso")
    c.add_argument("--out", "--uit", dest="uit", type=Path, help="output folder (default: next to the file)")
    c.add_argument("--quality", "--kwaliteit", dest="kwaliteit", default="medium", choices=list(QUALITY))
    c.add_argument("--target", "--doel", dest="doel", help="target size, e.g. 8MB or 500KB")
    c.add_argument("--from", "--van", dest="van", help="trim from (e.g. 0:10)")
    c.add_argument("--until", "--tot", dest="tot", help="trim until (e.g. 1:30)")
    c.add_argument("--height", "--hoogte", dest="hoogte", type=int, help="video height in pixels, e.g. 720")
    c.add_argument("--no-audio", "--zonder-geluid", dest="zonder_geluid", action="store_true")
    c.add_argument("--device", "--apparaat", dest="apparaat", help="video preset: iphone, android, psp, xbox, ...")
    c.add_argument("--scale", "--schaal", dest="schaal", type=float, help="scale an image in percent")
    c.add_argument("--width", "--breedte", dest="breedte", type=int)
    c.add_argument("--lang", "--taal", dest="taal", default="auto", help="speech to text: auto, en, nl, de, ...")
    c.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium"])
    c.add_argument("--translate", "--vertaal", dest="vertaal", action="store_true", help="translate speech to English")
    c.add_argument("--patch", type=Path, help="IPS/UPS/BPS patch for --to patch")
    m = c.add_argument_group("video/audio: codecs, frame rate and metadata")
    m.add_argument("--vcodec", choices=["h264", "h265", "av1", "vp9", "vp8", "prores", "dnxhd", "mpeg4", "mpeg2",
                                        "mjpeg", "theora", "copy"])
    m.add_argument("--fps", help="frame rate, e.g. 25, 29.97, 30, 60")
    m.add_argument("--vbitrate", help="video bitrate in kbps, e.g. 4000")
    m.add_argument("--crf", type=int, help="constant quality (lower = better), e.g. 23")
    m.add_argument("--preset", choices=["ultrafast", "veryfast", "fast", "medium", "slow", "veryslow"])
    m.add_argument("--10bit", dest="tenbit", action="store_true", help="10-bit colour (H.265/AV1/VP9)")
    m.add_argument("--all-streams", action="store_true", help="keep all audio tracks and subtitles")
    m.add_argument("--acodec", choices=["aac", "mp3", "opus", "vorbis", "flac", "alac", "ac3", "eac3", "pcm",
                                        "pcm24", "copy"])
    m.add_argument("--abitrate", help="audio bitrate in kbps, e.g. 192")
    m.add_argument("--sample-rate", help="e.g. 44100 or 48000")
    m.add_argument("--channels", help="mono, stereo, 5.1 or a number")
    m.add_argument("--volume", help="change the volume in dB, e.g. -3 or 6")
    m.add_argument("--strip-metadata", action="store_true", help="remove all tags and chapters (privacy)")
    for k in ("title", "artist", "album", "date", "genre", "comment"):
        m.add_argument(f"--{k}", dest=f"meta_{k}", help=f"set the {k} tag")

    f = sub.add_parser("formats", aliases=["formaten", "info"], help="what can this file become?")
    f.add_argument("bestand", type=Path, metavar="file")

    h = sub.add_parser("hash", aliases=["checksum"], help="checksums (MD5, SHA-256, CRC-32, ...)")
    h.add_argument("bestanden", nargs="+", type=Path, metavar="file")
    h.add_argument("--hmac", help="key for HMAC")

    p = sub.add_parser("pdf", help="PDF workbench: merge, split, rotate, delete, compress")
    p.add_argument("actie", type=_action(PDF_ACTIONS), metavar="{merge,split,rotate,delete,compress}")
    p.add_argument("bestanden", nargs="+", type=Path, metavar="file")
    p.add_argument("-o", "--output", "--uitvoer", dest="uitvoer", type=Path)
    p.add_argument("--pages", "--paginas", dest="paginas", default="", help="e.g. 1-3,5")
    p.add_argument("--angle", "--hoek", dest="hoek", type=int, default=90, choices=[90, 180, 270])
    p.add_argument("--target", "--doel", dest="doel", help="compress to e.g. 2MB")

    a = sub.add_parser("archive", aliases=["archief"], help="view, extract or create zip/7z/tar")
    a.add_argument("actie", type=_action(ARCHIVE_ACTIONS), metavar="{list,extract,pack}")
    a.add_argument("paden", nargs="+", type=Path, metavar="path")
    a.add_argument("-o", "--output", "--uitvoer", dest="uitvoer", type=Path)
    a.add_argument("--format", "--formaat", dest="formaat", default="zip",
                   choices=["zip", "7z", "tar.gz", "tar.xz", "tar.bz2", "tar"])

    s = sub.add_parser("social", help="photo/video at the exact size for a platform")
    s.add_argument("bestand", nargs="?", type=Path, metavar="file")
    s.add_argument("--size", "--formaat", dest="formaat", help="e.g. ig-story, ig-pano, yt-thumb (without: show the list)")
    s.add_argument("--fit", "--passend", dest="passend", action="store_true",
                   help="do not crop but fit (blurred background)")
    s.add_argument("--out", "--uit", dest="uit", type=Path)

    o = sub.add_parser("ocr", help="recognise text in an image, scan or screenshot")
    o.add_argument("bestand", nargs="?", type=Path, metavar="file")
    o.add_argument("--screen", "--scherm", dest="scherm", action="store_true", help="select an area of your screen")

    w = sub.add_parser("web", help="save a website as pdf/png/jpg")
    w.add_argument("url")
    w.add_argument("--to", "--naar", dest="naar", default="pdf", choices=["pdf", "png", "jpg"])
    w.add_argument("--out", "--uit", dest="uit", type=Path, default=Path.cwd())

    g = sub.add_parser("fetch", aliases=["ophalen"], help="video from a link, or a torrent (magnet / .torrent)")
    g.add_argument("bron", metavar="source")
    g.add_argument("--out", "--uit", dest="uit", type=Path, default=Path.home() / "Downloads")
    g.add_argument("--audio", action="store_true", help="audio only")
    g.add_argument("--no-scan", "--geen-scan", dest="geen_scan", action="store_true")

    q = sub.add_parser("sql", help="run SQL on a SQLite, .sql, CSV or Excel file (on a copy)")
    q.add_argument("bestand", type=Path, metavar="file")
    q.add_argument("opdracht", nargs="?", metavar="query", help="e.g. \"SELECT * FROM table\" (without: list the tables)")
    q.add_argument("--save", "--opslaan", dest="opslaan", type=Path, help="keep the changes as a new .sqlite")

    dr = sub.add_parser("drives", aliases=["schijven"], help="USB sticks, disks, CD/DVD: list, health, format")
    dr.add_argument("actie", choices=["list", "health", "format"], metavar="{list,health,format}")
    dr.add_argument("drive", nargs="?", help="device as shown by 'drives list', e.g. /dev/sdb, disk4 or 2")
    dr.add_argument("--fs", default="exfat", help="exfat (default), fat32, ntfs, ext4, apfs, hfs+")
    dr.add_argument("--label", default="USB", help="name of the new volume")
    dr.add_argument("--full", action="store_true", help="overwrite everything with zeros first (slow)")
    dr.add_argument("--internal", action="store_true", help="also allow internal (non-system) disks")
    dr.add_argument("--yes", metavar="DEVICE", help="confirm without asking by repeating the device name")

    v = sub.add_parser("scan", help="check a file or folder for viruses")
    v.add_argument("pad", type=Path, metavar="path")
    return ap


def run_command(args) -> int:
    try:
        return COMMANDS[args.cmd](args)
    except ConversionError as e:
        say("!! ERROR:", e)
        return 1
    except KeyboardInterrupt:
        say("\n!! stopped")
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
    for k, v in (("vcodec", a.vcodec), ("fps", a.fps), ("video_bitrate", a.vbitrate), ("crf", a.crf),
                 ("preset", a.preset), ("acodec", a.acodec), ("audio_bitrate", a.abitrate),
                 ("sample_rate", a.sample_rate), ("channels", a.channels), ("volume", a.volume),
                 *((f"meta_{k}", getattr(a, f"meta_{k}")) for k in ("title", "artist", "album", "date", "genre",
                                                                     "comment"))):
        if v not in (None, ""):
            opts[k] = v
    if a.tenbit:
        opts["pix_fmt"] = "10bit"
    if a.all_streams:
        opts["streams"] = "all"
    if a.strip_metadata:
        opts["metadata"] = "strip"
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
    if info["category"] in ("video", "audio"):
        try:
            from .media import media_info
            d = media_info(a.bestand)
            say(f"  container: {d['container']}, {d['duration']:.1f} s, {d['bitrate'] // 1000} kbps")
            for st in d["streams"]:
                bits = [st["kind"], (st["codec"] or "?") + (f" ({st['profile']})" if st.get("profile") else "")]
                if st["kind"] == "video":
                    bits += [f"{st['width']}x{st['height']}", f"{st['fps']} fps", st.get("pix_fmt") or ""]
                if st["kind"] == "audio":
                    bits += [f"{st['sample_rate']} Hz", st.get("layout") or f"{st.get('channels')} ch"]
                if st.get("bitrate"):
                    bits.append(f"{st['bitrate'] // 1000} kbps")
                say("  #" + str(st["index"]) + " " + ", ".join(b for b in bits if b))
            for k, v in d["tags"].items():
                say(f"  tag {k}: {v}")
        except ConversionError:
            pass
    say("can become:")
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
    if a.actie == "merge":
        dst = unique(a.uitvoer or src.with_name(f"{src.stem}_samengevoegd.pdf"))
        pdftools.merge(a.bestanden, dst)
    elif a.actie == "split":
        out_dir = a.uitvoer or src.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = pdftools.split(src, out_dir, a.paginas)
    elif a.actie in ("rotate", "delete"):
        dst = unique(a.uitvoer or src.with_name(f"{src.stem}_edited.pdf"))
        pdftools.edit_pages(src, dst, delete=a.paginas if a.actie == "delete" else "",
                            rotate=(a.paginas or "1-") if a.actie == "rotate" else "", angle=a.hoek)
    else:
        opts = {"format": "pdf", "quality": "low" if not a.doel else "medium"}
        if a.doel:
            opts["target_bytes"] = parse_size(a.doel, "mb")
        dst = convert_file(src, a.uitvoer, opts, Progress())
    say(f"OK: {dst} ({human_size(dst.stat().st_size)})")
    return 0


def cmd_archive(a) -> int:
    from .archive import _is_7z, _pack, _safe_extract
    if a.actie == "list":
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
            raise ConversionError("This is not a zip, 7z or tar archive.")
        for name, size in rows:
            say(f"  {human_size(size):>10}  {name}")
        say(f"{len(rows)} files, {human_size(sum(s for _, s in rows))} unpacked")
        return 0
    if a.actie == "extract":
        src = a.paden[0]
        dest = a.uitvoer or src.with_name(src.name.split(".")[0])
        dest.mkdir(parents=True, exist_ok=True)
        _safe_extract(src, dest)
        say(f"OK: extracted to {dest}")
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
            raise ConversionError("Choose a photo or video.")
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
        raise ConversionError("Give an image or PDF, or use --screen.")
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
        return f"!! VIRUS FOUND ({loc.get('engine')}): {loc.get('detail')}{extra}"
    if v["status"] == "clean":
        return f"✓ no virus found ({loc.get('engine')}){extra}"
    return f"? not sure: {loc.get('detail')}{extra}"


def cmd_scan(a) -> int:
    from . import virus
    from . import settings as user_settings
    v = virus.check(a.pad, user_settings.load().get("vt_key"))
    say(virus_line(v))
    for f in v["files"][:10]:
        say(f"  sha-256 {f['sha256']}  {f['name']}")
    return 2 if v["status"] == "infected" else 0


def cmd_drives(a) -> int:
    from . import drives
    if a.actie == "list":
        for d in drives.list_drives():
            ok, why = drives.formattable(d, a.internal)
            say(f"{d.id:<14} {d.name[:28]:<28} {human_size(d.size) if d.size else 'no medium':>10}  "
                f"{(d.bus or d.kind).upper():<8} {', '.join(d.labels + d.mounts)[:40]}")
            say(f"{'':14} {'can be formatted' if ok else 'not formattable: ' + why}")
        return 0
    if not a.drive:
        raise ConversionError("Give the drive, e.g. 'drives health /dev/sdb'. See 'drives list'.")
    if a.actie == "health":
        r = drives.health(a.drive)
        say(f"{a.drive}: {r['verdict']}" + (f" ({r['source']})" if r["source"] else ""))
        for line in r["lines"]:
            say("  " + line)
        return 0 if r["verdict"] in ("OK", "UNKNOWN", "N/A") else 2
    d = drives.find(a.drive)
    ok, why = drives.formattable(d, a.internal)
    if not ok:
        raise ConversionError(f"Not formatted: {why}.")
    say(f"FORMAT {d.id} · {d.name} · {human_size(d.size)} · {', '.join(d.labels + d.mounts)}")
    for c in drives.plan_format(d, a.fs, a.label, a.full):
        say("  will run: " + " ".join(c))
    confirm = a.yes
    if confirm is None:
        say("!! EVERYTHING on this drive will be deleted.")
        confirm = ask(f"type {d.id} to confirm (empty = cancel)")
    if not confirm:
        say("cancelled")
        return 1
    bar = Progress()
    msg = drives.format_drive(d.id, a.fs, a.label, confirm, a.full, a.internal, bar)
    bar.done()
    say("OK: " + msg)
    return 0


def parse(argv: list[str]) -> argparse.Namespace:
    first = next((a for a in argv if not a.startswith("-")), None)
    return build_parser(with_file=first not in COMMANDS).parse_args(argv)


def cmd_sql(a) -> int:
    from . import dbtool
    work = Path(tempfile.mkdtemp(prefix="ac-sql-"))
    try:
        db = dbtool.prepare(a.bestand.expanduser(), work)
        if not a.opdracht:
            for t in dbtool.overview(db):
                cols = ", ".join(c["naam"] + (f" {c['type']}" if c["type"] else "") for c in t["kolommen"])
                say(f"{t['soort']} {t['naam']} ({t['rijen']} rows): {cols}")
            return 0
        res = dbtool.query(db, a.opdracht)
        if res["kolommen"]:
            from .datafmt import write
            out = work / "uit.txt"
            write([dict(zip(res["kolommen"], r)) for r in res["rijen"]], out, "txt")
            print(out.read_text(encoding="utf-8"), end="")
            say(f"({len(res['rijen'])}{'+' if res['meer'] else ''} rows)")
        else:
            say(f"done: {res['opdrachten']} statement(s), {res['gewijzigd']} row(s) changed")
        if a.opslaan:
            dst = dbtool.export(db, "sqlite", work, a.opslaan.name)
            shutil.move(str(dst), a.opslaan)
            say(f"saved: {a.opslaan}")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


COMMANDS = {"converteer": cmd_convert, "convert": cmd_convert, "formaten": cmd_formats, "formats": cmd_formats,
            "info": cmd_formats, "hash": cmd_hash, "checksum": cmd_hash, "pdf": cmd_pdf, "archief": cmd_archive,
            "archive": cmd_archive, "social": cmd_social, "ocr": cmd_ocr, "web": cmd_web, "ophalen": cmd_fetch,
            "fetch": cmd_fetch, "scan": cmd_scan, "sql": cmd_sql,
            "drives": cmd_drives, "schijven": cmd_drives}


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
        say("   0) back")
    while True:
        raw = ask("choice")
        if raw.lower() in ("q", "stop", "exit", "quit"):
            raise SystemExit(0)
        if raw == "0" and allow_back:
            return -1
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        say("  choose a number from the list")


def ask_path(prompt: str, must_exist: bool = True) -> Path | None:
    while True:
        raw = ask(prompt + " (empty = back)")
        if not raw:
            return None
        p = Path(raw).expanduser()
        if not must_exist or p.exists():
            return p
        say(f"  does not exist: {p}")


def simple(version: str) -> int:
    say(f"ANYTHING CONVERTER {version} - eenvoudige modus")
    say("works in any terminal. q = quit. tip: drag a file into this window to paste its path.")
    menu = ["convert a file", "pdf: merge / split / rotate or delete pages",
            "social media size", "recognise text (ocr)", "download a video link or torrent",
            "virus scan or checksum", "archive: view / extract / pack", "save a website as pdf/png/jpg"]
    while True:
        try:
            k = choose("WHAT DO YOU WANT TO DO?", menu + ["quit"], allow_back=False)
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
        pp = ask("apply a patch (.ips/.ups/.bps)? path or empty")
        if pp:
            patch = Path(pp).expanduser()
            info = analyse(src, patch)
    k = choose("TO WHICH FORMAT?", [f".{x}  {fmt_label(info['category'], x)}" for x in info["targets"]])
    if k < 0:
        return
    fmt = info["targets"][k]
    opts: dict = {"format": fmt}
    cat = info["category"]
    if cat in ("video", "audio", "image", "pdf") and fmt not in ("txt", "srt", "vtt", "docx", "rtf", "xlsx"):
        g = choose("SIZE", ["quality high", "quality normal", "quality low", "target size (e.g. 8 MB)"])
        if g == 3:
            opts["target_bytes"] = parse_size(ask("target size", "8 MB"), "mb")
        elif g >= 0:
            opts["quality"] = ["high", "medium", "low"][g]
    if cat in ("video", "audio"):
        s, e = ask("trim from (empty = start)"), ask("trim to (empty = end)")
        if s:
            opts["trim_start"] = s
        if e:
            opts["trim_end"] = e
        if fmt in ("txt", "srt", "vtt"):
            opts["language"] = ask("language (auto, en, nl, de, fr, ...)", "auto")
            opts["speech_model"] = ask("model (base = fast, small = accurate)", "base")
    out = ask("output folder (empty = next to the file)")
    bar = Progress()
    dst = convert_file(src, Path(out).expanduser() if out else None, opts, bar, patch)
    bar.done()
    say(f"OK: {dst}")
    say(bars(src.stat().st_size, dst.stat().st_size))


def simple_pdf() -> None:
    k = choose("PDF", ["merge (pdfs and/or photos)", "split", "rotate pages", "delete pages",
                       "compress"])
    if k < 0:
        return
    args = argparse.Namespace(actie=["merge", "split", "rotate", "delete", "compress"][k],
                              uitvoer=None, paginas="", hoek=90, doel=None, bestanden=[])
    if k == 0:
        say("enter the files in order; empty = done")
        while True:
            p = ask_path(f"file {len(args.bestanden) + 1}")
            if not p:
                break
            args.bestanden.append(p)
        if len(args.bestanden) < 2:
            say("  at least two files needed")
            return
    else:
        p = ask_path("pdf")
        if not p:
            return
        args.bestanden = [p]
        if k == 1:
            args.paginas = ask("only these pages as one pdf (e.g. 1-3,5; empty = every page separately)")
        elif k in (2, 3):
            args.paginas = ask("which pages (e.g. 1-3,5)", "1-" if k == 2 else "")
            if k == 2:
                args.hoek = int(ask("angle (90, 180, 270)", "90"))
        elif k == 4:
            args.doel = ask("target size (empty = as small as possible)") or None
    cmd_pdf(args)


def simple_social() -> None:
    from . import social
    src = ask_path("photo or video")
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
    fit = choose("BIJSNIJDEN?", ["fill (crop from the centre)", "passend (alles zichtbaar, vage rand)"])
    cmd_social(argparse.Namespace(bestand=src, formaat=items[k][1], passend=fit == 1, uit=None))


def simple_ocr() -> None:
    k = choose("RECOGNISE TEXT", ["from an image or scan (pdf)", "from part of my screen"])
    if k < 0:
        return
    p = None if k == 1 else ask_path("image or pdf")
    if k == 0 and not p:
        return
    say("-" * 40)
    cmd_ocr(argparse.Namespace(bestand=p, scherm=k == 1))
    say("-" * 40)


def simple_fetch() -> None:
    src = ask("link, magnet:?... or path to .torrent (empty = back)")
    if not src:
        return
    audio = ask("audio only? (y/n)", "n").lower().startswith("j")
    out = Path(ask("save to", str(Path.home() / "Downloads"))).expanduser()
    cmd_fetch(argparse.Namespace(bron=src, uit=out, audio=audio, geen_scan=False))


def simple_scan() -> None:
    k = choose("CHECK", ["virusscan", "checksum (md5, sha-256, crc-32, ...)"])
    if k < 0:
        return
    p = ask_path("file or folder" if k == 0 else "bestand")
    if not p:
        return
    if k == 0:
        cmd_scan(argparse.Namespace(pad=p))
    else:
        cmd_hash(argparse.Namespace(bestanden=[p], hmac=ask("hmac key (empty = none)") or None))


def simple_archive() -> None:
    k = choose("ARCHIVE", ["view contents", "extract", "pack (zip, 7z, tar)"])
    if k < 0:
        return
    if k < 2:
        p = ask_path("archief")
        if not p:
            return
        out = None if k == 0 else Path(ask("extract to", str(p.with_name(p.name.split(".")[0]))))
        cmd_archive(argparse.Namespace(actie=["list", "extract"][k], paden=[p], uitvoer=out, formaat="zip"))
        return
    paden = []
    say("files or folders to pack; empty = done")
    while True:
        p = ask_path(f"pad {len(paden) + 1}")
        if not p:
            break
        paden.append(p)
    if not paden:
        return
    fmt = ["zip", "7z", "tar.gz", "tar.xz"][max(0, choose("FORMAT", ["zip", "7z", "tar.gz", "tar.xz"]))]
    cmd_archive(argparse.Namespace(actie="pack", paden=paden, uitvoer=None, formaat=fmt))


def simple_web() -> None:
    url = ask("website address (empty = back)")
    if not url:
        return
    k = choose("SAVE AS", ["pdf", "png", "jpg"])
    if k < 0:
        return
    cmd_web(argparse.Namespace(url=url, naar=["pdf", "png", "jpg"][k], uit=Path(ask("folder", str(Path.cwd())))))

