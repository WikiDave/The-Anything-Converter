"""Catalogus van ~1000 bestandsformaten: omschrijving, groep en hoe de converter ermee omgaat.

- omschrijvingen komen uit formaten.txt (één regel per extensie, per groep)
- dubbelzinnige extensies (.ts, .stl, .key, .md, .vcf, ...) worden aan de inhoud herkend
- onbekende of half gedownloade bestanden (.crdownload, .part, .tmp) ook aan de inhoud
"""
from __future__ import annotations

import re
import zipfile
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def catalog() -> dict[str, list[tuple[str, str]]]:
    """ext -> [(groep, omschrijving), ...]"""
    out: dict[str, list[tuple[str, str]]] = {}
    group = ""
    for line in (HERE / "formaten.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("*"):
            group = line
            continue
        m = re.match(r"\*\s+(.+?)\s+-\s+(.+)$", line)
        if not m:
            continue
        for ext in re.findall(r"\.([\w!.\-]+)", m.group(1)):
            out.setdefault(ext.lower(), []).append((group, m.group(2)))
    return out


def ext_of(path: Path) -> str:
    name = path.name.lower()
    for multi in ("tar.gz", "tar.bz2", "tar.xz", "tar.zst", "pkg.tar.zst", "tar.md5", "nii.gz", "osm.pbf",
                  "vma.zst"):
        if name.endswith("." + multi):
            return multi
    if name == "winmail.dat":
        return "tnef"
    return path.suffix.lower().lstrip(".")


def describe(path: Path | str) -> str:
    """Omschrijving voor de interface, bijv. 'Canon (Camera RAW)'."""
    ext = ext_of(Path(path))
    hits = catalog().get(ext)
    if not hits:
        return ""
    real = sniff(Path(path)) if Path(path).exists() else None
    if real and real != ext and catalog().get(real):
        hits = catalog()[real]
    seen, parts = set(), []
    for group, desc in hits:
        if desc not in seen:
            parts.append(f"{desc} ({group})")
            seen.add(desc)
    return "; ".join(parts[:2])


# --------------------------------------------------------------------------- inhoud herkennen

SIGNATURES = [  # (offset, bytes, ext)
    (0, b"%PDF-", "pdf"), (0, b"\x89PNG\r\n\x1a\n", "png"), (0, b"\xff\xd8\xff", "jpg"), (0, b"GIF8", "gif"),
    (0, b"BM", "bmp"), (0, b"II*\x00", "tiff"), (0, b"MM\x00*", "tiff"), (0, b"8BPS", "psd"),
    (0, b"\x00\x00\x01\x00", "ico"), (0, b"icns", "icns"), (0, b"qoif", "qoi"), (0, b"DDS ", "dds"),
    (0, b"v/1\x01", "exr"), (0, b"#?RADIANCE", "hdr"), (0, b"\xff\x0a", "jxl"),
    (0, b"\x00\x00\x00\x0cJXL ", "jxl"), (0, b"\x00\x00\x00\x0cjP  ", "jp2"), (0, b"gimp xcf", "xcf"),
    (0, b"Rar!\x1a\x07", "rar"), (0, b"7z\xbc\xaf\x27\x1c", "7z"), (0, b"\x1f\x8b", "gz"), (0, b"BZh", "bz2"),
    (0, b"\xfd7zXZ\x00", "xz"), (0, b"\x28\xb5\x2f\xfd", "zst"), (0, b"\x04\x22\x4d\x18", "lz4"),
    (0, b"MSCF", "cab"), (0, b"xar!", "xar"), (0, b"070707", "cpio"), (0, b"070701", "cpio"),
    (0, b"!<arch>\n", "ar"), (0, b"\xed\xab\xee\xdb", "rpm"), (0, b"Cr24", "crx"),
    (0, b"fLaC", "flac"), (0, b"ID3", "mp3"), (0, b"\xff\xfb", "mp3"), (0, b"\xff\xf3", "mp3"),
    (0, b"OggS", "ogg"), (0, b"MAC ", "ape"), (0, b"wvpk", "wv"), (0, b"TTA1", "tta"), (0, b"MPCK", "mpc"),
    (0, b"DSD ", "dsf"), (0, b"FRM8", "dff"), (0, b"#!AMR", "amr"), (0, b".snd", "au"), (0, b"caff", "caf"),
    (0, b"MThd", "mid"), (0, b"\x1aE\xdf\xa3", "mkv"), (0, b"FLV", "flv"), (0, b"FWS", "swf"), (0, b"CWS", "swf"),
    (0, b"\x30\x26\xb2\x75\x8e\x66\xcf\x11", "asf"), (0, b".RMF", "rm"), (0, b"\x00\x00\x01\xba", "mpg"),
    (0, b"\x00\x00\x01\xb3", "mpg"), (0, b"YUV4MPEG2", "y4m"), (0, b"DKIF", "ivf"), (0, b"BIK", "bik"),
    (0, b"wOFF", "woff"), (0, b"wOF2", "woff2"), (0, b"ttcf", "ttc"), (0, b"OTTO", "otf"),
    (0, b"\x00\x01\x00\x00\x00", "ttf"), (0, b"SQLite format 3\x00", "sqlite"), (0, b"PAR2", "par2"),
    (0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole"), (0, b"MZ", "exe"), (0, b"\x7fELF", "elf"),
    (0, b"\xfe\xed\xfa", "macho"), (0, b"\xcf\xfa\xed\xfe", "macho"), (0, b"\xca\xfe\xba\xbe", "class"),
    (0, b"\x00asm", "wasm"), (0, b"\x78\x9f\x3e\x22", "tnef"), (0, b"BEGIN:VCARD", "vcf"),
    (0, b"BEGIN:VCALENDAR", "ics"), (0, b"-----BEGIN CERTIFICATE", "pem"), (0, b"-----BEGIN ", "pem"),
    (0, b"ssh-", "pub"), (0, b"ecdsa-sha2", "pub"), (0, b"PuTTY-User-Key-File", "ppk"),
    (0, b"bplist00", "plist"), (0, b"QFI\xfb", "qcow2"), (0, b"KDMV", "vmdk"), (0, b"conectix", "vhd"),
    (0, b"vhdxfile", "vhdx"), (0, b"<<< Oracle VM VirtualBox Disk Image >>>", "vdi"),
    (0, b"koly", "dmg"), (0, b"GGUF", "gguf"), (0, b"\x93NUMPY", "npy"), (0, b"SIMPLE  =", "fits"),
    (0, b"AT&TFORM", "djvu"), (0, b"PK\x03\x04", "zip"), (0, b"PK\x05\x06", "zip"), (128, b"DICM", "dcm"),
    (257, b"ustar", "tar"), (8, b"WEBP", "webp"), (8, b"AVI ", "avi"), (8, b"WAVE", "wav"), (8, b"AIFF", "aiff"),
    (8, b"AIFC", "aifc"), (4, b"ftypheic", "heic"), (4, b"ftypheix", "heic"), (4, b"ftypmif1", "heic"),
    (4, b"ftypavif", "avif"), (4, b"ftypqt", "mov"), (4, b"ftypM4A", "m4a"), (4, b"ftypM4V", "m4v"),
    (4, b"ftyp3g", "3gp"), (4, b"ftypcrx", "cr3"), (4, b"ftyp", "mp4"), (0, b"\x47", "ts?"),
    (0, b"\x0a\x05\x01\x08", "pcx"), (0, b"\x59\xa6\x6a\x95", "ras"), (0, b"\x01\xda", "sgi"),
    (0, b"P1", "pbm"), (0, b"P4", "pbm"), (0, b"P2", "pgm"), (0, b"P5", "pgm"), (0, b"P3", "ppm"), (0, b"P6", "ppm"),
    (0, b"#define", "xbm"), (0, b"/* XPM */", "xpm"), (0, b"OBJ", "obj?"), (0, b"solid ", "stl?"),
    (0, b"ply\n", "ply"), (0, b"glTF", "glb"), (0, b"Kaydara FBX Binary", "fbx"), (0, b"BLENDER", "blend"),
    (0, b"\x4d\x4d", "3ds?"), (0, b"AC10", "dwg"), (0, b"%!PS", "ps"), (0, b"\xc5\xd0\xd3\xc6", "eps"),
    (0, b"\x01\x00\x00\x00", "emf?"), (0, b"\xd7\xcd\xc6\x9a", "wmf"), (0, b"OFXHEADER", "ofx"),
    (0, b"d8:announce", "torrent"), (0, b"d4:info", "torrent"), (0, b"\xd4\xc3\xb2\xa1", "pcap"),
    (0, b"\xa1\xb2\xc3\xd4", "pcap"), (0, b"\x0a\x0d\x0d\x0a", "pcapng"), (0, b"NES\x1a", "nes"),
    (0, b"\x80\x37\x12\x40", "z64"), (0, b"\x37\x80\x40\x12", "v64"), (0, b"\x40\x12\x37\x80", "n64"),
    (0, b"CISO", "cso"), (0, b"MComprHD", "chd"), (0, b"\x00PBP", "pbp"), (0, b"WBFS", "wbfs"),
    (0, b"RVZ\x01", "rvz"), (0, b"PATCH", "ips"), (0, b"UPS1", "ups"), (0, b"BPS1", "bps"),
    (0, b"UF2\n", "uf2"), (0, b"\x89HDF\r\n\x1a\n", "h5"), (0, b"CDF\x01", "nc"), (0, b"CDF\x02", "nc"),
    (0, b"PAR1", "parquet"), (0, b"ARROW1", "arrow"), (0, b"Obj\x01", "avro"), (0, b"ORC", "orc"),
    (0, b"\x03\xd9\xa2\x9a", "kdbx"), (0, b"DICM", "dcm"),
]

TEXT_HINTS = [  # (regex op het begin van een tekstbestand, ext)
    (r"^\s*<\?xml[^>]*>\s*<gpx\b", "gpx"), (r"<gpx\b", "gpx"), (r"<kml\b", "kml"),
    (r"<TrainingCenterDatabase", "tcx"), (r"^\s*\{\s*\"type\"\s*:\s*\"(Feature|FeatureCollection)", "geojson"),
    (r"^\s*<\?xml[^>]*>\s*<(tt|tt:tt)\b", "ttml"), (r"<svg\b", "svg"), (r"<rss\b", "rss"), (r"<feed\b", "atom"),
    (r"<opml\b", "opml"), (r"<map version=\"(freeplane|\d)", "mm"), (r"<playlist[^>]*xspf", "xspf"),
    (r"^<\?wpl", "wpl"), (r"^\s*<asx\b", "asx"), (r"<plist\b", "plist"), (r"^\s*<\?xml", "xml"),
    (r"^\s*<(!doctype html|html)\b", "html"), (r"^WEBVTT", "vtt"), (r"^\[Script Info\]", "ass"),
    (r"^1\s*\r?\n\d\d:\d\d:\d\d[,.]\d+ --> ", "srt"), (r"^\d+:\d\d:\d\d\.\d+,\d+:\d\d:\d\d\.\d+\r?\n", "sbv"),
    (r"^\{\d+\}\{\d+\}", "sub"), (r"^\[\d\d:\d\d[.:]\d\d", "lrc"), (r"^#EXTM3U", "m3u"), (r"^\[playlist\]", "pls"),
    (r"^BEGIN:VCARD", "vcf"), (r"^BEGIN:VCALENDAR", "ics"), (r"^##fileformat=VCF", "vcf-gen"),
    (r"^-----BEGIN PGP", "asc"), (r"^-----BEGIN ", "pem"), (r"^(ssh-(rsa|ed25519|dss)|ecdsa-sha2)", "pub"),
    (r"^Version \d+\s*\nSHEET", "asc-ltspice"), (r"^:[0-9A-F]{10}", "hex"), (r"^S[0-9][0-9A-F]{6}", "srec"),
    (r"^(G0|G1|G21|G90|M\d{2,3}|;FLAVOR|; generated)", "gcode"), (r"^OFXHEADER|<OFX>", "ofx"),
    (r"^!Type:", "qif"), (r"^:20:", "sta"), (r"^0000\d", "cod"), (r"^%PDF", "pdf"), (r"^\s*[\{\[]", "json"),
    (r"^ID;P", "slk"), (r"^TABLE\r?\n0,1", "dif"), (r"^digraph|^graph|^strict (di)?graph", "gv"),
    (r"^@startuml", "puml"), (r"^(graph|flowchart|sequenceDiagram|classDiagram|gantt|pie)\b", "mmd"),
    (r"^\.TH |^\.\\\"", "man"), (r"^HEADER {4}|^ATOM  ", "pdb-protein"), (r"^>\S", "fasta"), (r"^@\S+\n[ACGTN]", "fastq"),
    (r"^AFCOLHR|^AFCOD", "igc"),
]


def _head(path: Path, n: int = 4096) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read(n)
    except OSError:
        return b""


def looks_text(data: bytes) -> bool:
    if not data:
        return False
    if data.startswith((b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")):
        return True
    if b"\x00" in data[:2048]:
        return False
    bad = sum(1 for b in data[:2048] if b < 9 or 13 < b < 32)
    return bad < len(data[:2048]) * 0.02


def zip_kind(path: Path) -> str | None:
    """Wat voor zip is het? (docx, epub, apk, kmz, ...)"""
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            mt = z.read("mimetype").decode(errors="ignore").strip() if "mimetype" in names else ""
    except Exception:  # noqa: BLE001
        return None
    if mt == "application/epub+zip":
        return "epub"
    for key, ext in (("opendocument.text", "odt"), ("opendocument.spreadsheet", "ods"),
                     ("opendocument.presentation", "odp"), ("opendocument.graphics", "odg"), ("image/openraster", "ora"),
                     ("application/x-krita", "kra")):
        if key in mt:
            return ext
    if "word/document.xml" in names:
        return "docx"
    if "xl/workbook.xml" in names or "xl/workbook.bin" in names:
        return "xlsx"
    if "ppt/presentation.xml" in names:
        return "pptx"
    if "AndroidManifest.xml" in names:
        return "apk"
    if any(n.startswith("Payload/") for n in names):
        return "ipa"
    if "doc.kml" in names or any(n.endswith(".kml") for n in names):
        return "kmz"
    if "3D/3dmodel.model" in names:
        return "3mf"
    if "Index/Document.iwa" in names or any(n.startswith("Index/") for n in names):
        return "iwork"
    if "META-INF/MANIFEST.MF" in names:
        return "jar"
    if any(n.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) for n in names) and \
            all(n.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", "/", ".xml", ".txt")) for n in names):
        return "cbz"
    return "zip"


def sniff(path: Path) -> str | None:
    """Echte soort bestand aan de hand van de inhoud (None als onbekend)."""
    head = _head(path)
    if not head:
        return None
    for off, sig, ext in SIGNATURES:
        if head[off:off + len(sig)] == sig:
            if ext == "zip":
                return zip_kind(path) or "zip"
            if ext == "ts?":
                return "ts" if len(head) > 376 and head[188:189] == b"\x47" else None
            if ext in ("obj?", "stl?", "3ds?", "emf?"):
                if ext == "stl?" and looks_text(head):
                    return "stl"
                if ext == "emf?" and head[40:44] == b" EMF":
                    return "emf"
                if ext == "3ds?" and len(head) > 6:
                    return "3ds-model"
                continue
            if ext == "ole":
                return _ole_kind(path)
            return ext
    if head[80:84] and len(head) >= 84 and not looks_text(head[:80]):
        # binaire STL: 80 bytes kop + aantal driehoeken; grootte klopt precies
        n = int.from_bytes(head[80:84], "little")
        if path.stat().st_size == 84 + n * 50 and n > 0:
            return "stl"
    if looks_text(head):
        text = head.decode("utf-8", "ignore")
        for pat, ext in TEXT_HINTS:
            if re.search(pat, text[:2000], re.I | re.M if ext not in ("srt", "sbv") else re.M):
                return ext
        return "txt"
    return None


def _ole_kind(path: Path) -> str:
    """Oud Office-bestand (OLE): Word, Excel, PowerPoint, Outlook, Visio, Publisher, MSI?"""
    data = _head(path, 1 << 20)
    for marker, ext in ((b"W\x00o\x00r\x00d\x00D\x00o\x00c\x00u\x00m\x00e\x00n\x00t", "doc"),
                        (b"W\x00o\x00r\x00k\x00b\x00o\x00o\x00k", "xls"), (b"B\x00o\x00o\x00k", "xls"),
                        (b"P\x00o\x00w\x00e\x00r\x00P\x00o\x00i\x00n\x00t", "ppt"),
                        (b"_\x00_\x00s\x00u\x00b\x00s\x00t\x00g", "msg"),
                        (b"V\x00i\x00s\x00i\x00o\x00D\x00o\x00c\x00u\x00m\x00e\x00n\x00t", "vsd"),
                        (b"P\x00u\x00b\x00l\x00i\x00s\x00h\x00e\x00r", "pub"),
                        (b"\x05\x00S\x00u\x00m\x00m\x00a\x00r\x00y", "ole")):
        if marker in data:
            return ext
    return "ole"
