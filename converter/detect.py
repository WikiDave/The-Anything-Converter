"""Bepaal de categorie van een bestand en welke uitvoerformaten mogelijk zijn."""
from __future__ import annotations

from pathlib import Path

from .util import ffprobe, ConversionError

VIDEO = {"mp4", "m4v", "mov", "mkv", "webm", "avi", "wmv", "flv", "mpg", "mpeg", "3gp", "ts", "mts", "m2ts", "ogv", "vob"}
AUDIO = {"mp3", "wav", "flac", "aac", "m4a", "ogg", "oga", "opus", "wma", "aiff", "aif", "amr", "alac"}
IMAGE = {"jpg", "jpeg", "png", "webp", "gif", "bmp", "tif", "tiff", "ico", "avif", "heic", "heif", "jfif", "tga", "ppm", "psd", "svg"}
PDF = {"pdf"}
DOCUMENT = {"doc", "docx", "odt", "rtf", "txt", "md", "markdown", "html", "htm", "epub", "tex", "rst"}
SPREADSHEET = {"xls", "xlsx", "ods", "csv", "tsv"}
PRESENTATION = {"ppt", "pptx", "odp", "key"}
ARCHIVE = {"zip", "tar", "gz", "tgz", "bz2", "tbz2", "xz", "txz"}

TARGETS = {
    "video": ["mp4", "webm", "mkv", "mov", "avi", "gif", "mp3", "m4a", "wav", "ogg"],
    "audio": ["mp3", "m4a", "aac", "wav", "flac", "ogg", "opus"],
    "image": ["jpg", "png", "webp", "avif", "gif", "bmp", "tiff", "ico", "pdf"],
    "pdf": ["pdf", "docx", "odt", "txt", "html", "png", "jpg"],
    "document": ["pdf", "docx", "odt", "rtf", "txt", "html", "md", "epub"],
    "spreadsheet": ["xlsx", "ods", "csv", "pdf", "html"],
    "presentation": ["pdf", "pptx", "odp"],
    "archive": ["zip", "tar.gz", "tar.bz2", "tar.xz", "tar"],
    "other": ["zip", "tar.gz", "tar.xz"],
}

LABELS = {
    "video": "Video", "audio": "Audio", "image": "Afbeelding", "pdf": "PDF",
    "document": "Document", "spreadsheet": "Spreadsheet", "presentation": "Presentatie",
    "archive": "Archief", "other": "Overig bestand",
}


def extension(path: Path | str) -> str:
    name = Path(path).name.lower()
    for multi in ("tar.gz", "tar.bz2", "tar.xz"):
        if name.endswith("." + multi):
            return multi
    return Path(name).suffix.lstrip(".")


def detect(path: Path) -> str:
    ext = extension(path)
    for cat, exts in (("video", VIDEO), ("audio", AUDIO), ("image", IMAGE), ("pdf", PDF),
                      ("document", DOCUMENT), ("spreadsheet", SPREADSHEET),
                      ("presentation", PRESENTATION)):
        if ext in exts:
            return cat
    if ext in ARCHIVE or ext in ("tar.gz", "tar.bz2", "tar.xz"):
        return "archive"
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
