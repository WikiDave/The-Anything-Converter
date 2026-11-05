"""Verdeelt bestanden over de juiste omzetter, op extensie én inhoud.

Dubbelzinnige extensies worden aan de inhoud herkend: .ts (video of TypeScript), .stl (3D of ondertitels),
.key (Keynote of sleutel), .pub (Publisher of SSH-sleutel), .md (Markdown of Mega Drive), .vcf (contacten of
DNA-varianten), .gpx (GPS of Guitar Pro), .dot (Word-sjabloon of Graphviz), .vhd (Hyper-V of VHDL), ...
Half gedownloade of hernoemde bestanden (.crdownload, .part, .tmp, geen extensie) ook.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import datafmt, objfmt, subsfmt, textfmt, unpack
from .catalog import catalog, ext_of, looks_text, sniff

FAMILY_LABELS = {
    "text": "Text / code", "data": "Data", "subtitle": "Subtitles", "playlist": "Playlist", "midi": "MIDI",
    "font": "Font", "mail": "E-mail", "contact": "Contacts", "calendar": "Calendar", "gps": "GPS / map",
    "model3d": "3D model", "cad": "CAD drawing", "vector": "Vector image", "cert": "Certificate / key",
    "medical": "Medical image (DICOM)", "compressed": "Compressed file", "archive2": "Archive / package",
    "vmdisk": "VM disk", "comic": "Comic book", "info": "Other file",
}

LO_VECTOR = {"odg", "vsd", "vsdx", "vssx", "pub", "cdr", "emf", "wmf", "cgm", "otg"}
TEMP_EXT = {"crdownload", "part", "partial", "download", "!ut", "!qb", "tmp", "temp", "bak", "old", "cache", "dat",
            "", "bin-onbekend", "file"}

FAMILY_EXT: dict[str, str] = {}
for _fam, _exts in (("subtitle", subsfmt.SUBS - {"sub", "stl"}), ("playlist", subsfmt.PLAYLISTS),
                    ("midi", subsfmt.MIDI), ("font", objfmt.FONTS), ("mail", objfmt.MAIL - {"tnef"}),
                    ("contact", objfmt.CONTACT), ("calendar", objfmt.CALENDAR), ("gps", objfmt.GPS),
                    ("model3d", objfmt.MODEL3D - {"stl"}), ("cad", objfmt.CAD),
                    ("vector", (objfmt.VECTOR | LO_VECTOR) - {"pub"}), ("cert", objfmt.CERT - {"key", "pub"}),
                    ("medical", objfmt.MEDICAL),
                    ("data", (datafmt.TREE | datafmt.DB | datafmt.SPECIAL | datafmt.FINANCE) - {"csv", "tsv", "conf"}),
                    ("compressed", unpack.COMPRESSED), ("archive2", unpack.ARCHIVES | unpack.PACKAGES),
                    ("vmdisk", unpack.VMDISKS), ("comic", unpack.COMICS), ("text", textfmt.WEB | textfmt.MAN |
                                                                           textfmt.NFO | {"md", "markdown", "mdx"})):
    for _e in _exts:
        FAMILY_EXT[_e] = _fam
FAMILY_EXT["tnef"] = "mail"
for _e in ("pkl", "pickle", "joblib", "torrent"):
    FAMILY_EXT[_e] = "info"


def effective_ext(path: Path) -> str:
    """De extensie waarmee we het bestand behandelen (bij een onduidelijke extensie: die van de inhoud)."""
    ext = ext_of(path)
    known = ext in catalog() or ext in FAMILY_EXT
    if ext in TEMP_EXT or not known:
        real = sniff(path)
        if real and real not in ("txt", "ole", "zip") and real not in TEMP_EXT:
            return real.replace("pdb-protein", "pdb").replace("vcf-gen", "vcf-gen")
        if real == "zip" and ext in TEMP_EXT:
            return "zip"
    return ext


def classify(path: Path) -> tuple[str, str] | None:
    """(categorie, effectieve extensie) voor families die niet in detect.py staan; None = laat detect.py beslissen."""
    ext = ext_of(path)
    eff = effective_ext(path)
    real = sniff(path) if path.exists() else None

    # dubbelzinnige extensies
    if ext == "ts":
        return None if real == "ts" else ("text", "ts")
    if ext == "stl":
        head = path.read_bytes()[:8]
        return ("subtitle", "stl") if head[3:6] == b"STL" else ("model3d", "stl")
    if ext == "key":
        return None if real in ("iwork", "zip") else ("cert", "key")
    if ext == "pub":
        return ("cert", "pub") if real == "pub" else ("vector", "pub")
    if ext == "md":
        return ("text", "md") if real in ("txt", None) or looks_text(path.read_bytes()[:4096]) else None
    if ext == "vcf":
        return ("text", "vcf") if real == "vcf-gen" else ("contact", "vcf")
    if ext == "gpx":
        return ("gps", "gpx") if real == "gpx" else ("info", "gpx")
    if ext == "dot":
        return ("vector", "gv") if real in ("gv", "txt") else None
    if ext == "vhd":
        return ("text", "vhd") if looks_text(path.read_bytes()[:4096]) else ("vmdisk", "vhd")
    if ext == "sub":
        return ("subtitle", "sub") if looks_text(path.read_bytes()[:4096]) else ("info", "sub")
    if ext == "nc":
        return ("text", "nc") if real in ("txt", "gcode") else ("info", "nc")
    if ext in ("mm",):
        return ("data", "xml") if real in ("mm", "xml") else ("text", "mm")
    if ext == "dat" and real == "tnef":
        return ("mail", "tnef")
    if ext in ("pdb", "asc"):
        if looks_text(path.read_bytes()[:4096]):
            return ("text", ext)
        return None if ext == "pdb" else ("info", ext)
    if ext == "raw":
        return None if _rawpy_ok(path) else ("info", "raw")
    if ext in ("3ds",):
        return ("info", ext)
    if ext == "conf":
        return ("text", "conf")

    from .detect import KNOWN_EXT
    from .rom import DISC_EXT, ROM_EXT
    if eff in DISC_EXT or eff in ROM_EXT or eff == "bin":
        return None if eff == ext else (None, eff)
    if eff in KNOWN_EXT:
        return None if eff == ext else (None, eff)  # bekend type (video, audio, ...) onder een andere naam
    if eff in FAMILY_EXT:
        return FAMILY_EXT[eff], eff
    if eff in ("zip", "7z", "tar", "gz") and ext != eff:
        return None
    try:
        head = path.read_bytes()[:4096]
    except OSError:
        return ("info", eff)
    if looks_text(head):
        return ("text", eff)
    return ("info", eff)


def _rawpy_ok(path: Path) -> bool:
    try:
        import rawpy
        with rawpy.imread(str(path)):
            return True
    except Exception:  # noqa: BLE001
        return False


def targets(path: Path, category: str, eff: str) -> list[str]:
    if category == "text":
        return textfmt.targets(eff)
    if category == "data":
        return datafmt.targets(eff)
    if category in ("subtitle", "playlist", "midi"):
        return subsfmt.targets(eff)
    if category in ("font", "mail", "contact", "calendar", "gps", "model3d", "cad", "vector", "cert", "medical"):
        out = objfmt.targets({"font": "font", "mail": "mail"}.get(category, category), eff)
        if category == "font" and "otf" in out and not objfmt.is_cff(path):
            out.remove("otf")
        if category == "vector" and eff in LO_VECTOR:
            out = ["pdf", "png", "svg", "jpg"]
        return out
    if category in ("compressed", "archive2", "vmdisk", "comic"):
        return unpack.targets(category, eff)
    return ["txt", "zip", "7z"]  # info: rapport, of inpakken


def with_ext(src: Path, eff: str, work: Path) -> Path:
    """Een kopie (of link) met de juiste extensie, zodat de omzetter weet wat het is."""
    if not eff or src.suffix.lower().lstrip(".") == eff or ext_of(src) == eff:
        return src
    work.mkdir(parents=True, exist_ok=True)
    stem = src.name.split(".")[0] or "bestand"
    dst = work / f"{stem}.{eff}"
    try:
        dst.hardlink_to(src)
    except OSError:
        shutil.copyfile(src, dst)
    return dst


def process(src: Path, out_dir: Path, category: str, eff: str, opts: dict, progress=None) -> Path:
    from .util import ConversionError
    fmt = (opts.get("format") or "").lower()
    if progress:
        progress(0.1, "converting")
    if category == "info" or fmt == "rapport":
        if fmt in ("zip", "7z"):
            from .archive import _pack
            dst = out_dir / f"{src.name}.{fmt}"
            _pack([src], src.parent, dst, fmt, 9)
            return dst
        from .info import report
        dst = out_dir / f"{src.stem}_info.txt"
        dst.write_text(report(src), encoding="utf-8")
        return dst
    src = with_ext(src, eff, out_dir / "_in")
    if category == "text":
        return textfmt.convert(src, out_dir, fmt, opts)
    if category == "data":
        return datafmt.convert(src, out_dir, fmt, opts)
    if category in ("subtitle", "playlist", "midi"):
        return subsfmt.convert(src, out_dir, fmt, opts)
    if category == "vector" and eff in LO_VECTOR:
        from .document import libreoffice
        pdf = libreoffice(src, "pdf", out_dir)
        if fmt == "pdf":
            dst = out_dir / f"{src.stem}.pdf"
            shutil.move(str(pdf), dst)
            return dst
        return objfmt.vector(pdf, out_dir, fmt)
    if category in ("font", "mail", "contact", "calendar", "gps", "model3d", "cad", "vector", "cert", "medical"):
        return objfmt.convert(category, src, out_dir, fmt, opts)
    if category in ("compressed", "archive2", "vmdisk", "comic"):
        return unpack.convert(category, src, out_dir, fmt, opts)
    raise ConversionError(f"Unknown kind: {category}")
