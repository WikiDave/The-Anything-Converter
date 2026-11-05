"""Gedeelde uitleg bij formaten en de lijst met mogelijke uitvoer per bestand (terminal en CLI)."""
from __future__ import annotations

from pathlib import Path

from .detect import LABELS

FMT_LABEL = {
    "docx": "Word", "doc": "Word 97-2003", "odt": "OpenDocument text", "xlsx": "Excel", "xls": "Excel 97-2003",
    "ods": "OpenDocument spreadsheet", "pptx": "PowerPoint", "ppt": "PowerPoint 97-2003",
    "odp": "OpenDocument presentation", "rtf": "Rich Text", "txt": "plain text", "html": "web page", "xml": "XML",
    "md": "Markdown", "csv": "CSV", "epub": "e-book", "mobi": "Kindle (old)", "azw3": "Kindle", "fb2": "FictionBook",
    "lit": "Microsoft Reader", "lrf": "Sony Reader", "pdb": "Palm", "tcr": "Psion", "pdf": "PDF",
    "svg": "SVG (vector wrapper)", "eps": "PostScript", "tga": "Targa", "wbmp": "WAP bitmap",
    "exr": "OpenEXR (HDR)", "hdr": "Radiance HDR", "ico": "icon / favicon", "m4r": "iPhone ringtone",
    "mmf": "ringtone (SMAF)", "wma": "Windows Media Audio", "aiff": "Apple audio", "wmv": "Windows Media Video",
    "flv": "Flash video", "mpg": "MPEG-2", "ogv": "Ogg video", "3gp": "old phones", "3g2": "old phones",
    "srt": "subtitles", "vtt": "subtitles (web)", "7z": "7-Zip", "zip": "zip", "iso": "ISO (datatrack)",
    "cue": "one BIN + CUE (merged)", "chd": "CHD (compact, for RetroArch/MAME/DuckStation)", "cso": "CSO (PSP, compressed)",
    "z64": "N64 big-endian", "v64": "N64 byteswapped", "n64": "N64 little-endian", "sfc": "SNES without copier header",
    "smc": "SNES with copier header", "nds": "trimmed", "patch": "apply patch (IPS/UPS/BPS)",
    "mp4": "video (plays everywhere)", "webm": "video for the web", "mkv": "Matroska", "mov": "QuickTime",
    "avi": "AVI", "gif": "animatie", "mp3": "MP3", "m4a": "AAC (Apple)", "aac": "AAC", "wav": "WAV",
    "flac": "FLAC (lossless)", "ogg": "Ogg Vorbis", "opus": "Opus", "jpg": "JPEG", "png": "PNG", "webp": "WebP",
    "avif": "AVIF", "bmp": "BMP", "tiff": "TIFF", "tar": "tar", "tar.gz": "tar + gzip", "tar.bz2": "tar + bzip2",
    "tar.xz": "tar + xz", "bin": "Mega Drive (plain)",
    "uitpakken": "extract (original file)",
    "json-mooi": "JSON, neatly indented",
    "yaml-mooi": "YAML, tidy",
    "xml-mooi": "XML, neatly indented",
    "sql": "SQL dump",
    "py": "Python",
    "plist": "macOS plist",
    "lrc": "lyrics",
    "sbv": "YouTube subtitles",
    "ttml": "XML subtitles",
    "ass": "styled subtitles",
    "m3u8": "playlist (UTF-8)",
    "pls": "playlist",
    "xspf": "playlist (XML)",
    "wpl": "Windows playlist",
    "kml": "Google Earth",
    "kmz": "Google Earth (zip)",
    "gpx": "GPS route",
    "geojson": "geodata",
    "tcx": "Garmin",
    "stl": "3D printing",
    "obj": "3D model",
    "ply": "3D model / scan",
    "glb": "3D for web/AR",
    "off": "3D model",
    "3mf": "3D print project",
    "woff": "web font",
    "woff2": "web font (small)",
    "ttf": "TrueType",
    "otf": "OpenType",
    "pem": "text (PEM)",
    "der": "binary (DER)",
    "eml": "e-mail message",
    "qcow2": "QEMU/Proxmox",
    "vmdk": "VMware",
    "vdi": "VirtualBox",
    "vhdx": "Hyper-V",
    "vhd": "Hyper-V (old)",
    "raw": "raw disk",
    "cbz": "comic book",
    "yaml": "YAML",
    "toml": "TOML",
    "json": "JSON",
    "eac3": "Dolby Digital Plus",
    "ac3": "Dolby Digital",
    "wv": "WavPack (lossless)",
    "tta": "True Audio (lossless)",
    "au": "Unix audio",
    "caf": "Apple Core Audio",
    "mka": "Matroska audio",
    "m4b": "audiobook",
    "spx": "Speex speech",
    "alac": "Apple Lossless (.m4a)",
    "m4v": "Apple video",
    "asf": "Windows Media",
    "ts": "MPEG transport stream",
    "m2ts": "Blu-ray/AVCHD",
    "mxf": "broadcast",
    "divx": "DivX",
    "rapport": "info report",
}


def fmt_label(cat: str, t: str) -> str:
    if t in ("txt", "srt", "vtt") and cat in ("video", "audio"):
        return "speech to text" if t == "txt" else "speech to subtitles"
    if cat == "image" and t in ("txt", "docx", "rtf", "xlsx"):
        return "recognise text (OCR) → " + FMT_LABEL.get(t, t)
    if cat == "pdf" and t == "pdf":
        return "compress / shrink PDF"
    if cat == "pdf" and t in ("png", "jpg"):
        return "every page as an image"
    if cat == "disc" and t == "wav":
        return "audio tracks as WAV"
    if cat == "rom" and t == "md":
        return "Mega Drive (gewoon)"
    if cat == "info" and t == "txt":
        return "info report (what it is, details, checksums)"
    if cat in ("archive2", "compressed", "vmdisk") and t == "txt":
        return "list of contents"
    if cat == "text" and t == "png":
        return "as an image (e.g. NFO art)"
    if cat == "text" and t == "html":
        return "web page with colours"
    return FMT_LABEL.get(t, "")


def analyse(path: Path, patch: Path | None = None) -> dict:
    """Categorie, label en mogelijke uitvoer van een bestand (zoals de web-interface ze krijgt)."""
    from .detect import targets_for
    cat, eff, targets = targets_for(path, [patch] if patch else [])
    return {"category": cat, "label": LABELS.get(cat, cat), "targets": targets, "ext": eff}
