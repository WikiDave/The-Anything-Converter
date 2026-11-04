"""Bepaal de categorie van een bestand en welke uitvoerformaten mogelijk zijn."""
from __future__ import annotations

from pathlib import Path

from .util import ffprobe, ConversionError

VIDEO = {"mp4", "m4v", "mov", "mkv", "webm", "avi", "wmv", "flv", "mpg", "mpeg", "3gp", "ts", "mts", "m2ts", "ogv", "vob"}
AUDIO = {"mp3", "wav", "flac", "aac", "m4a", "ogg", "oga", "opus", "wma", "aiff", "aif", "amr", "alac"}
IMAGE = {"jpg", "jpeg", "png", "webp", "gif", "bmp", "tif", "tiff", "ico", "avif", "heic", "heif", "jfif", "tga", "ppm", "psd", "svg"}
PDF = {"pdf"}
DOCUMENT = {"doc", "docx", "odt", "rtf", "txt", "md", "markdown", "html", "htm", "tex", "rst", "wpd", "pages"}
EBOOK = {"epub", "mobi", "azw", "azw3", "azw4", "fb2", "lit", "lrf", "pdb", "tcr", "prc", "snb", "cbz", "cbr"}
SPREADSHEET = {"xls", "xlsx", "ods", "csv", "tsv"}
PRESENTATION = {"ppt", "pptx", "odp", "key"}
ARCHIVE = {"zip", "tar", "gz", "tgz", "bz2", "tbz2", "xz", "txz", "7z"}

TARGETS = {
    "video": ["mp4", "webm", "mkv", "mov", "avi", "wmv", "flv", "mpg", "ogv", "3gp", "3g2", "gif",
              "mp3", "m4a", "aac", "wav", "flac", "ogg", "opus", "aiff", "wma", "m4r", "mmf", "txt", "srt", "vtt"],
    "audio": ["mp3", "m4a", "aac", "wav", "flac", "ogg", "opus", "aiff", "wma", "m4r", "mmf", "txt", "srt", "vtt"],
    "image": ["jpg", "png", "webp", "avif", "gif", "bmp", "tiff", "ico", "pdf", "svg", "eps", "tga", "wbmp",
              "exr", "hdr", "txt", "docx", "rtf", "xlsx"],
    "pdf": ["pdf", "docx", "xlsx", "pptx", "png", "jpg", "rtf", "txt", "html", "xml", "odt"],
    "document": ["pdf", "docx", "doc", "odt", "rtf", "txt", "html", "md", "epub", "mobi", "azw3", "fb2"],
    "spreadsheet": ["xlsx", "xls", "ods", "csv", "pdf", "html"],
    "presentation": ["pdf", "pptx", "ppt", "odp", "png", "jpg"],
    "ebook": ["epub", "mobi", "azw3", "fb2", "pdf", "docx", "txt", "html", "rtf", "lit", "lrf", "pdb", "tcr"],
    "archive": ["zip", "7z", "tar.gz", "tar.bz2", "tar.xz", "tar"],
    "other": ["zip", "7z", "tar.gz", "tar.xz"],
}

LABELS = {
    "video": "Video", "audio": "Audio", "image": "Afbeelding", "pdf": "PDF",
    "document": "Document", "spreadsheet": "Spreadsheet", "presentation": "Presentatie", "ebook": "E-book",
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
                      ("ebook", EBOOK), ("document", DOCUMENT), ("spreadsheet", SPREADSHEET),
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
