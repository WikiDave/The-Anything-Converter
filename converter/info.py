"""Inforapport voor elk bestand: wat het is, wat erin zit, checksums - ook voor formaten die niet om te zetten zijn
(programma's, projectbestanden van andere apps, versleutelde bestanden, AI-modellen, ...)."""
from __future__ import annotations

import json
import re
import struct
import zipfile
from pathlib import Path

from .util import human_size

# Waarom iets niet omgezet kan worden (per soort), voor in het rapport en de interface
WHY = {
    "project": "Projectbestand van een ander programma: alleen dat programma kan het openen. Wel: checksums, "
               "inpakken, en bij zip-projecten de inhoud bekijken.",
    "program": "Programma of systeembestand: niets om te converteren. Wel: details, checksums en een virusscan.",
    "encrypted": "Versleuteld of beveiligd (DRM): openen kan alleen met de juiste sleutel of het originele programma.",
    "proprietary": "Gesloten formaat zonder openbare beschrijving; alleen het eigen programma kan het lezen.",
    "model": "AI-model: details en checksums; omzetten tussen AI-formaten vraagt de bijbehorende frameworks.",
    "shortcut": "Snelkoppeling: toont waar hij naartoe wijst.",
}
ENCRYPTED = {"m4p", "acsm", "kfx", "kdbx", "kdb", "gpg", "pgp", "crypt14", "crypt15", "1pux", "nsp", "xci", "nsz",
             "cia", "3ds", "pfx", "p12", "jks", "keystore", "p8", "snk", "ppk", "shsh2", "ab", "ipd", "bbb", "pst",
             "ost", "olm", "nsf", "accde", "mobileprovision", "provisionprofile", "intunewin"}
PROGRAM = {"exe", "dll", "sys", "drv", "ocx", "cpl", "scr", "com", "efi", "so", "dylib", "a", "o", "ko", "elf", "out",
           "class", "pyc", "pyd", "wasm", "xll", "8bf", "vst3", "component", "clap", "kext", "app", "framework",
           "bundle", "prefpane", "saver", "mui", "nls", "msstyles", "gadget", "xex", "xbe"}
MODEL = {"gguf", "ggml", "safetensors", "pt", "pth", "ckpt", "onnx", "keras", "tflite", "mlmodel", "mlpackage", "pb",
         "h5", "joblib", "pkl", "pickle"}


def report(path: Path) -> str:
    from .catalog import describe, ext_of, sniff
    from .hashes import compute
    ext = ext_of(path)
    real = sniff(path)
    lines = [f"BESTAND     {path.name}", f"GROOTTE     {human_size(path.stat().st_size)} ({path.stat().st_size} bytes)"]
    desc = describe(path)
    if desc:
        lines.append(f"SOORT       {desc}")
    if real and real != ext:
        lines.append(f"INHOUD      lijkt op .{real} (herkend aan de inhoud)")
    reason = ("encrypted" if ext in ENCRYPTED else "program" if ext in PROGRAM else "model" if ext in MODEL else None)
    if reason:
        lines.append(f"LET OP      {WHY[reason]}")
    extra = []
    try:
        extra = details(path, ext, real)
    except Exception as e:  # noqa: BLE001
        extra = [f"(details lezen lukte niet: {e})"]
    if extra:
        lines += ["", "DETAILS"] + [f"  {x}" for x in extra]
    if path.stat().st_size <= 2 * 1024 ** 3:
        lines += ["", "CHECKSUMS"] + [f"  {k:<11} {v}" for k, v in compute(path).items()
                                      if k in ("CRC-32", "MD5", "SHA-1", "SHA-256")]
    return "\n".join(lines) + "\n"


def details(path: Path, ext: str, real: str | None) -> list[str]:
    head = path.read_bytes()[:65536] if path.stat().st_size else b""
    kind = real or ext
    if head[:2] == b"MZ":
        return _pe(path)
    if head[:4] == b"\x7fELF":
        bits = 64 if head[4] == 2 else 32
        etype = {1: "objectbestand", 2: "programma", 3: "gedeelde bibliotheek", 4: "core dump"}.get(head[16], "?")
        mach = {0x3E: "x86-64", 0xB7: "ARM64", 0x28: "ARM", 0x03: "x86", 0xF3: "RISC-V"}.get(
            struct.unpack_from("<H", head, 18)[0], "?")
        return [f"Linux/Unix ELF, {bits}-bit, {etype}, processor {mach}"]
    if head[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
        return ["macOS Mach-O programma of bibliotheek" + (" (universeel: meerdere processors)"
                                                            if head[:4] == b"\xca\xfe\xba\xbe" else "")]
    if kind == "gguf" or head[:4] == b"GGUF":
        return _gguf(path)
    if ext == "safetensors":
        n = struct.unpack_from("<Q", head, 0)[0]
        meta = json.loads(path.read_bytes()[8:8 + n])
        tensors = {k: v for k, v in meta.items() if k != "__metadata__"}
        params = sum(_prod(v.get("shape", [])) for v in tensors.values())
        dtypes = sorted({v.get("dtype") for v in tensors.values()})
        return [f"{len(tensors)} tensors, {params / 1e6:.1f} miljoen parameters, types: {', '.join(dtypes)}"] + \
            [f"{k}: {v}" for k, v in list(meta.get("__metadata__", {}).items())[:10]]
    if ext in ("pkl", "pickle", "joblib"):
        return ["Python-pickle: wordt bewust niet geopend, want een pickle kan code uitvoeren op je computer."]
    if ext == "torrent" or head[:11] in (b"d8:announce",) or head[:7] == b"d4:info":
        return _torrent(path.read_bytes())
    if ext in ("lnk",):
        return _lnk(head)
    if ext in ("url", "webloc", "desktop", "gdoc", "gsheet", "gslides", "appref-ms", "flatpakref"):
        text = path.read_text(errors="replace")
        urls = re.findall(r"(https?://[^\s\"'<>]+)", text)
        return [f"wijst naar: {u}" for u in urls[:5]] or [text[:500]]
    if head[:8] == b"bplist00" or ext in ("plist", "mobileconfig"):
        import plistlib
        try:
            data = plistlib.loads(path.read_bytes())
            return [f"{k}: {str(v)[:120]}" for k, v in list(data.items())[:25]] if isinstance(data, dict) else []
        except Exception:  # noqa: BLE001
            return []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            out = [f"zip met {len(infos)} bestanden, {human_size(sum(i.file_size for i in infos))} uitgepakt"]
            out += [f"{human_size(i.file_size):>10}  {i.filename}" for i in infos[:40]]
            if len(infos) > 40:
                out.append(f"... en nog {len(infos) - 40}")
            return out
    if head[:15] == b"SQLite format 3":
        from .datafmt import sqlite_tables
        return [f"tabel {n}: {len(rows)} rijen, kolommen: {', '.join(c)}" for n, (c, rows) in sqlite_tables(path).items()]
    from .catalog import looks_text
    if looks_text(head):
        text = head.decode("utf-8", "replace")
        n = text.count("\n")
        return [f"tekstbestand, eerste regels:"] + [x[:150] for x in text.splitlines()[:15]] + \
            ([f"(± {path.stat().st_size // max(1, len(head) // max(1, n)):,} regels)"] if n else [])
    return []


def _prod(shape) -> int:
    out = 1
    for x in shape:
        out *= int(x)
    return out


def _pe(path: Path) -> list[str]:
    try:
        import pefile
    except ImportError:
        return ["Windows-programma of -bibliotheek (PE)"]
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"],
                                           pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_SECURITY"]])
    mach = {0x14C: "x86 (32-bit)", 0x8664: "x64", 0xAA64: "ARM64"}.get(pe.FILE_HEADER.Machine, hex(pe.FILE_HEADER.Machine))
    kind = "DLL" if pe.is_dll() else "driver" if pe.is_driver() else "programma"
    out = [f"Windows {kind}, {mach}"]
    import datetime
    ts = pe.FILE_HEADER.TimeDateStamp
    if 0 < ts < 4e9:
        out.append(f"gebouwd: {datetime.datetime.fromtimestamp(ts, datetime.timezone.utc):%Y-%m-%d}")
    for fi in getattr(pe, "FileInfo", []) or []:
        for entry in fi:
            for st in getattr(entry, "StringTable", []):
                for k, v in st.entries.items():
                    k, v = k.decode(errors="ignore"), v.decode(errors="ignore")
                    if k in ("CompanyName", "FileDescription", "FileVersion", "ProductName", "ProductVersion",
                             "LegalCopyright", "OriginalFilename") and v:
                        out.append(f"{k}: {v}")
    sec = pe.OPTIONAL_HEADER.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_SECURITY"]]
    out.append("digitaal ondertekend: " + ("ja" if sec.Size else "nee"))
    data = path.read_bytes()
    if b"Nullsoft" in data[:1 << 20]:
        out.append("installer: NSIS (inhoud uitpakken kan met 7-Zip)")
    elif b"Inno Setup" in data[:1 << 20]:
        out.append("installer: Inno Setup")
    return out


def _gguf(path: Path) -> list[str]:
    with open(path, "rb") as f:
        f.read(4)
        ver = struct.unpack("<I", f.read(4))[0]
        n_tensors, n_kv = struct.unpack("<QQ", f.read(16))
        out = [f"GGUF versie {ver}, {n_tensors} tensors"]

        def rstr():
            n = struct.unpack("<Q", f.read(8))[0]
            return f.read(n).decode("utf-8", "replace")

        def rval(t):
            fmt = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
            if t in fmt:
                return struct.unpack(fmt[t], f.read(struct.calcsize(fmt[t])))[0]
            if t == 8:
                return rstr()
            if t == 9:
                it = struct.unpack("<I", f.read(4))[0]
                n = struct.unpack("<Q", f.read(8))[0]
                vals = [rval(it) for _ in range(min(n, 1_000_000))]
                return f"[{n} waarden]" if n > 8 else vals
            raise ValueError
        for _ in range(min(n_kv, 200)):
            key = rstr()
            t = struct.unpack("<I", f.read(4))[0]
            val = rval(t)
            if any(x in key for x in ("name", "architecture", "context_length", "parameter", "quantization",
                                       "file_type", "license", "block_count", "embedding_length")):
                out.append(f"{key}: {val}")
    return out


def _lnk(head: bytes) -> list[str]:
    if head[:4] != b"\x4c\x00\x00\x00":
        return []
    strings = re.findall(rb"(?:[A-Za-z]:\\|\\\\)[\x20-\x7e]{3,200}", head)
    uni = re.findall(rb"(?:[A-Za-z]\x00:\x00\\\x00)(?:[\x20-\x7e]\x00){3,200}", head)
    found = [s.decode("latin-1") for s in strings] + [u.decode("utf-16-le", "ignore") for u in uni]
    return [f"wijst naar: {x}" for x in dict.fromkeys(found)][:3] or ["Windows-snelkoppeling"]


def _bdecode(data: bytes, i: int = 0):
    c = data[i:i + 1]
    if c == b"i":
        j = data.index(b"e", i)
        return int(data[i + 1:j]), j + 1
    if c == b"l":
        out, i = [], i + 1
        while data[i:i + 1] != b"e":
            v, i = _bdecode(data, i)
            out.append(v)
        return out, i + 1
    if c == b"d":
        out, i = {}, i + 1
        while data[i:i + 1] != b"e":
            k, i = _bdecode(data, i)
            v, i = _bdecode(data, i)
            out[k] = v
        return out, i + 1
    j = data.index(b":", i)
    n = int(data[i:j])
    return data[j + 1:j + 1 + n], j + 1 + n


def _torrent(data: bytes) -> list[str]:
    meta, _ = _bdecode(data)
    info = meta.get(b"info", {})
    name = info.get(b"name", b"").decode("utf-8", "replace")
    files = info.get(b"files") or [{b"length": info.get(b"length", 0), b"path": [name.encode()]}]
    total = sum(f.get(b"length", 0) for f in files)
    out = [f"torrent: {name}, {len(files)} bestanden, {human_size(total)}"]
    if meta.get(b"announce"):
        out.append(f"tracker: {meta[b'announce'].decode('utf-8', 'replace')}")
    for f in files[:40]:
        out.append(f"{human_size(f.get(b'length', 0)):>10}  " + "/".join(p.decode("utf-8", "replace")
                                                                       for p in f.get(b"path", [])))
    return out
