"""Bepaal de categorie van een bestand en welke uitvoerformaten mogelijk zijn."""
from __future__ import annotations

from pathlib import Path

from .util import ffprobe, ConversionError

VIDEO = {"mp4", "m4v", "mov", "mkv", "webm", "avi", "wmv", "flv", "mpg", "mpeg", "3gp", "3g2", "ts", "mts", "m2ts",
         "ogv", "vob", "qt", "mk3d", "asf", "f4v", "swf", "mpe", "m1v", "m2v", "evo", "rm", "rmvb", "divx", "dv", "vro",
         "mxf", "h264", "h265", "hevc", "y4m", "ivf", "insv", "360", "lrv", "dav", "bik"}
AUDIO = {"mp3", "wav", "flac", "aac", "m4a", "ogg", "oga", "opus", "wma", "aiff", "aif", "amr", "alac", "aifc", "m4b",
         "m4p", "m4r", "ape", "wv", "tta", "mpc", "dsf", "dff", "mka", "ac3", "eac3", "thd", "dts", "awb", "3ga", "gsm",
         "spx", "au", "snd", "ra", "weba", "caf", "bwf", "w64", "rf64", "voc", "mod", "xm", "it", "s3m", "mmf"}
RAW = {"dng", "cr2", "cr3", "crw", "nef", "nrw", "arw", "srf", "sr2", "raf", "orf", "rw2", "pef", "srw", "rwl", "3fr",
       "fff", "iiq", "x3f", "erf", "mrw", "kdc", "dcr", "mos", "gpr", "raw"}
IMAGE = {"jpg", "jpeg", "png", "webp", "gif", "bmp", "tif", "tiff", "ico", "avif", "heic", "heif", "jfif", "tga", "ppm",
         "psd", "jpe", "apng", "jxl", "jp2", "j2k", "jpx", "jxr", "wdp", "hdp", "mpo", "dib", "cur", "icns", "pcx",
         "pbm", "pgm", "pnm", "xbm", "xpm", "wbmp", "pict", "pct", "sgi", "rgb", "ras", "qoi", "hdr", "exr", "dds",
         "psb", "xcf", "kra", "ora", "fits", "fit-beeld", "thm", "insp", "procreate", "blp", "pcd", "msp"} | RAW
PDF = {"pdf"}
DOCUMENT = {"doc", "docx", "odt", "rtf", "txt", "tex", "rst", "wpd", "pages", "docm", "dot", "dotx", "dotm", "ott",
            "sxw", "wps", "abw", "lwp", "hwp"}
EBOOK = {"epub", "mobi", "azw", "azw3", "azw4", "fb2", "lit", "lrf", "pdb", "tcr", "prc", "snb", "kfx", "ibooks",
         "djvu", "fbz"}
SPREADSHEET = {"xls", "xlsx", "ods", "csv", "tsv", "xlsm", "xlsb", "xlt", "xltx", "xltm", "ots", "sxc", "numbers",
               "123", "wk1", "wks", "qpw", "slk", "dif"}
PRESENTATION = {"ppt", "pptx", "odp", "key", "pptm", "pps", "ppsx", "ppsm", "pot", "potx", "potm", "otp", "sxi"}
ARCHIVE = {"zip", "tar", "tgz", "tbz2", "txz", "7z"}
KNOWN_EXT = VIDEO | AUDIO | IMAGE | PDF | DOCUMENT | EBOOK | SPREADSHEET | PRESENTATION | ARCHIVE | {"tar.gz", "tar.bz2",
                                                                                                   "tar.xz"}

TARGETS = {
    "video": ["mp4", "webm", "mkv", "mov", "avi", "m4v", "wmv", "asf", "flv", "mpg", "ts", "m2ts", "mxf", "divx",
              "ogv", "3gp", "3g2", "gif", "mp3", "m4a", "aac", "wav", "flac", "ogg", "opus", "aiff", "wma", "ac3",
              "mka", "m4r", "mmf", "txt", "srt", "vtt"],
    "audio": ["mp3", "m4a", "aac", "wav", "flac", "alac", "ogg", "opus", "aiff", "wma", "ac3", "eac3", "wv", "tta",
              "au", "caf", "mka", "m4b", "spx", "m4r", "mmf", "txt", "srt", "vtt"],
    "image": ["jpg", "png", "webp", "avif", "gif", "bmp", "tiff", "ico", "pdf", "svg", "eps", "tga", "wbmp",
              "exr", "hdr", "txt", "docx", "rtf", "xlsx"],
    "pdf": ["pdf", "docx", "xlsx", "pptx", "png", "jpg", "rtf", "txt", "html", "xml", "odt"],
    "document": ["pdf", "docx", "doc", "odt", "rtf", "txt", "html", "md", "epub", "mobi", "azw3", "fb2"],
    "spreadsheet": ["xlsx", "xls", "ods", "csv", "pdf", "html"],
    "presentation": ["pdf", "pptx", "ppt", "odp", "png", "jpg"],
    "ebook": ["epub", "mobi", "azw3", "fb2", "pdf", "docx", "txt", "html", "rtf", "lit", "lrf", "pdb", "tcr"],
    "archive": ["zip", "7z", "tar.gz", "tar.bz2", "tar.xz", "tar"],
    "disc": ["iso", "cue", "zip"],  # precies per bestand: converter.rom.targets
    "rom": ["zip", "7z"],
    "other": ["zip", "7z", "tar.gz", "tar.xz"],
}

LABELS = {
    "video": "Video", "audio": "Audio", "image": "Image", "pdf": "PDF",
    "document": "Document", "spreadsheet": "Spreadsheet", "presentation": "Presentation", "ebook": "E-book",
    "disc": "Disc image (emulator)", "rom": "ROM (emulator)",
    "archive": "Archive", "other": "Other file",
}



def extension(path: Path | str) -> str:
    name = Path(path).name.lower()
    for multi in ("tar.gz", "tar.bz2", "tar.xz"):
        if name.endswith("." + multi):
            return multi
    return Path(name).suffix.lstrip(".")


def analyse_path(path: Path) -> tuple[str, str]:
    """(categorie, effectieve extensie). De extensie kan afwijken bij half gedownloade/hernoemde bestanden."""
    from .families import classify
    ext = extension(path)
    try:
        r = classify(path) if Path(path).exists() else None
    except Exception:  # noqa: BLE001 - herkennen mag nooit de upload laten mislukken
        r = None
    if r is None:
        return _detect_ext(path, ext), ext
    cat, eff = r
    if cat is None:
        return _detect_ext(path, eff), eff
    return cat, eff


def detect(path: Path) -> str:
    return analyse_path(path)[0]


def _detect_ext(path: Path, ext: str) -> str:
    from . import rom
    if ext in rom.DISC_EXT or (ext == "bin" and rom.is_disc_bin(path)):
        return "disc"
    if ext in rom.ROM_EXT or ext == "bin":
        return "rom"
    for cat, exts in (("video", VIDEO), ("audio", AUDIO), ("image", IMAGE), ("pdf", PDF),
                      ("ebook", EBOOK), ("document", DOCUMENT), ("spreadsheet", SPREADSHEET),
                      ("presentation", PRESENTATION)):
        if ext in exts:
            return cat
    if ext in ARCHIVE or ext in ("tar.gz", "tar.bz2", "tar.xz"):
        return "archive"
    if ext in ("gz", "bz2", "xz"):
        return "compressed"
    # Onbekende extensie: laat ffprobe kijken of het media is.
    try:
        info = ffprobe(path)
        kinds = {s.get("codec_type") for s in info.get("streams", [])}
        fmt = info.get("format", {}).get("format_name", "")
        if "video" in kinds and not fmt.startswith("image2") and float(info["format"].get("duration", 0) or 0) > 0:
            return "video"
        if "audio" in kinds:
            return "audio"
        if "video" in kinds:
            return "image"
    except (ConversionError, KeyError, ValueError):
        pass
    return "other"


def media_info(path: Path) -> dict:
    """Korte samenvatting voor de interface."""
    try:
        info = ffprobe(path)
    except ConversionError:
        return {}
    fmt = info.get("format", {})
    out = {"duration": float(fmt.get("duration", 0) or 0)}
    for s in info.get("streams", []):
        if s.get("codec_type") == "video" and "width" not in out:
            out.update(width=s.get("width"), height=s.get("height"), vcodec=s.get("codec_name"))
        elif s.get("codec_type") == "audio" and "acodec" not in out:
            out.update(acodec=s.get("codec_name"))
    return out


def targets_for(path: Path, patches=()) -> tuple[str, str, list[str]]:
    """(categorie, effectieve extensie, mogelijke uitvoer) voor één bestand."""
    from . import families, rom
    cat, eff = analyse_path(path)
    if patches and cat not in ("disc", "rom"):
        cat = "rom"
    if cat in families.FAMILY_LABELS:
        return cat, eff, families.targets(Path(path), cat, eff)
    if cat in ("disc", "rom"):
        return cat, eff, rom.targets(Path(path), cat, list(patches))
    out = list(TARGETS.get(cat, TARGETS["other"]))
    if cat == "video":
        info = media_info(Path(path))
        if info and not info.get("acodec"):  # video zonder geluid: geen audio of spraak aanbieden
            from .media import AUDIO_ONLY
            out = [t for t in out if t not in AUDIO_ONLY and t not in ("txt", "srt", "vtt")]
    if eff in ("csv", "tsv"):
        out += ["json", "yaml", "xml", "txt"]
    if cat == "image" and eff in ("gif", "webp", "apng", "png"):
        try:  # animated image: can also become a video
            from PIL import Image
            with Image.open(path) as im:
                if getattr(im, "n_frames", 1) > 1:
                    out = out[:1] + ["mp4", "webm", "mov"] + out[1:]
        except Exception:  # noqa: BLE001
            pass
    return cat, eff, out


# Labels van de extra families (na alle definities: voorkomt een kringverwijzing bij het importeren)
from .families import FAMILY_LABELS  # noqa: E402
LABELS.update(FAMILY_LABELS)
