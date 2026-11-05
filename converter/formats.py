"""Gedeelde uitleg bij formaten en de lijst met mogelijke uitvoer per bestand (terminal en CLI)."""
from __future__ import annotations

from pathlib import Path

from .detect import LABELS

FMT_LABEL = {
    "docx": "Word", "doc": "Word 97-2003", "odt": "OpenDocument-tekst", "xlsx": "Excel", "xls": "Excel 97-2003",
    "ods": "OpenDocument-rekenblad", "pptx": "PowerPoint", "ppt": "PowerPoint 97-2003",
    "odp": "OpenDocument-presentatie", "rtf": "Rich Text", "txt": "platte tekst", "html": "webpagina", "xml": "XML",
    "md": "Markdown", "csv": "CSV", "epub": "e-book", "mobi": "Kindle (oud)", "azw3": "Kindle", "fb2": "FictionBook",
    "lit": "Microsoft Reader", "lrf": "Sony Reader", "pdb": "Palm", "tcr": "Psion", "pdf": "PDF",
    "svg": "SVG (vector-verpakking)", "eps": "PostScript", "tga": "Targa", "wbmp": "WAP-bitmap",
    "exr": "OpenEXR (HDR)", "hdr": "Radiance HDR", "ico": "pictogram / favicon", "m4r": "iPhone-beltoon",
    "mmf": "beltoon (SMAF)", "wma": "Windows Media Audio", "aiff": "Apple-audio", "wmv": "Windows Media Video",
    "flv": "Flash-video", "mpg": "MPEG-2", "ogv": "Ogg-video", "3gp": "oude telefoons", "3g2": "oude telefoons",
    "srt": "ondertitels", "vtt": "ondertitels (web)", "7z": "7-Zip", "zip": "zip", "iso": "ISO (datatrack)",
    "cue": "één BIN + CUE (samengevoegd)", "chd": "CHD (RetroArch/MAME/DuckStation)", "cso": "CSO (PSP)",
    "z64": "N64 big-endian", "v64": "N64 byteswapped", "n64": "N64 little-endian", "sfc": "SNES zonder header",
    "smc": "SNES met header", "nds": "ingekort (trim)", "patch": "patch toepassen (IPS/UPS/BPS)",
    "mp4": "video (overal afspeelbaar)", "webm": "video voor het web", "mkv": "Matroska", "mov": "QuickTime",
    "avi": "AVI", "gif": "animatie", "mp3": "MP3", "m4a": "AAC (Apple)", "aac": "AAC", "wav": "WAV (verliesvrij)",
    "flac": "FLAC (verliesvrij)", "ogg": "Ogg Vorbis", "opus": "Opus", "jpg": "JPEG", "png": "PNG", "webp": "WebP",
    "avif": "AVIF", "bmp": "BMP", "tiff": "TIFF", "tar": "tar", "tar.gz": "tar + gzip", "tar.bz2": "tar + bzip2",
    "tar.xz": "tar + xz", "bin": "Mega Drive (gewoon)",
    "uitpakken": "uitpakken (origineel bestand)",
    "json-mooi": "JSON netjes ingesprongen",
    "yaml-mooi": "YAML netjes",
    "xml-mooi": "XML netjes ingesprongen",
    "sql": "SQL-dump",
    "py": "Python",
    "plist": "macOS-plist",
    "lrc": "songtekst",
    "sbv": "YouTube-ondertitels",
    "ttml": "XML-ondertitels",
    "ass": "opgemaakte ondertitels",
    "m3u8": "afspeellijst (UTF-8)",
    "pls": "afspeellijst",
    "xspf": "afspeellijst (XML)",
    "wpl": "Windows-afspeellijst",
    "kml": "Google Earth",
    "kmz": "Google Earth (zip)",
    "gpx": "GPS-route",
    "geojson": "geodata",
    "tcx": "Garmin",
    "stl": "3D-printen",
    "obj": "3D-model",
    "ply": "3D-model / scan",
    "glb": "3D voor web/AR",
    "off": "3D-model",
    "3mf": "3D-printproject",
    "woff": "weblettertype",
    "woff2": "weblettertype (klein)",
    "ttf": "TrueType",
    "otf": "OpenType",
    "pem": "tekst (PEM)",
    "der": "binair (DER)",
    "eml": "e-mailbericht",
    "qcow2": "QEMU/Proxmox",
    "vmdk": "VMware",
    "vdi": "VirtualBox",
    "vhdx": "Hyper-V",
    "vhd": "Hyper-V (oud)",
    "raw": "ruwe schijf",
    "cbz": "stripboek",
    "yaml": "YAML",
    "toml": "TOML",
    "json": "JSON",
    "eac3": "Dolby Digital Plus",
    "ac3": "Dolby Digital",
    "wv": "WavPack (verliesvrij)",
    "tta": "True Audio (verliesvrij)",
    "au": "Unix-audio",
    "caf": "Apple Core Audio",
    "mka": "Matroska-audio",
    "m4b": "audioboek",
    "spx": "Speex-spraak",
    "alac": "Apple Lossless (.m4a)",
    "m4v": "Apple-video",
    "asf": "Windows Media",
    "ts": "MPEG-transportstream",
    "m2ts": "Blu-ray/AVCHD",
    "mxf": "broadcast",
    "divx": "DivX",
    "rapport": "inforapport",
}


def fmt_label(cat: str, t: str) -> str:
    if t in ("txt", "srt", "vtt") and cat in ("video", "audio"):
        return "spraak naar tekst" if t == "txt" else "spraak naar ondertitels"
    if cat == "image" and t in ("txt", "docx", "rtf", "xlsx"):
        return "tekst herkennen (OCR) → " + FMT_LABEL.get(t, t)
    if cat == "pdf" and t == "pdf":
        return "PDF comprimeren / verkleinen"
    if cat == "pdf" and t in ("png", "jpg"):
        return "elke pagina als afbeelding"
    if cat == "disc" and t == "wav":
        return "audiosporen als WAV"
    if cat == "rom" and t == "md":
        return "Mega Drive (gewoon)"
    if cat == "info" and t == "txt":
        return "inforapport (wat is het, details, checksums)"
    if cat in ("archive2", "compressed", "vmdisk") and t == "txt":
        return "lijst met de inhoud"
    if cat == "text" and t == "png":
        return "als afbeelding (bijv. NFO-art)"
    if cat == "text" and t == "html":
        return "webpagina met kleuren"
    return FMT_LABEL.get(t, "")


def analyse(path: Path, patch: Path | None = None) -> dict:
    """Categorie, label en mogelijke uitvoer van een bestand (zoals de web-interface ze krijgt)."""
    from .detect import targets_for
    cat, eff, targets = targets_for(path, [patch] if patch else [])
    return {"category": cat, "label": LABELS.get(cat, cat), "targets": targets, "ext": eff}
