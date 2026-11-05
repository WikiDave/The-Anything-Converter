"""Uitpakken en opnieuw inpakken: archieven, pakketten, schijf- en VM-images, stripboeken, losse compressie.

Volgorde: Python zelf (zip, tar, 7z, gz/bz2/xz, ar/deb, uu, ...), dan 7-Zip (meegeleverd in de desktop-app:
RAR, CAB, DMG, WIM, VHD(X), VMDK, VDI, QCOW2, MSI, CHM, RPM, XAR/PKG, NSIS, SquashFS, ISO/UDF, ...),
dan bsdtar (macOS/Windows hebben die standaard). VM-schijven omzetten (qcow2, vmdk, vdi, vhdx) gaat met qemu-img.
"""
from __future__ import annotations

import bz2
import gzip
import io
import lzma
import re
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

from .util import NO_WINDOW, ConversionError, have

COMPRESSED = {"gz", "bz2", "xz", "lzma", "zst", "lz4", "br", "z", "lz", "lzo"}
ARCHIVES = {"rar", "r00", "r01", "001", "zipx", "cab", "arj", "lzh", "lha", "ace", "arc", "xar", "cpio", "squashfs",
            "uue", "uu", "hqx", "sit", "sitx", "tzst", "tar.zst", "pkg.tar.zst", "tar.md5", "ar"}
PACKAGES = {"jar", "war", "ear", "whl", "egg", "nupkg", "vsix", "xpi", "crx", "apk", "aab", "xapk", "apks", "apkm",
            "ipa", "appx", "appxbundle", "msix", "msixbundle", "deb", "rpm", "gem", "unitypackage", "ova", "pkg",
            "mpkg", "xip", "msi", "msp", "msu", "cab", "chm", "sb3", "mcpack", "mcaddon", "mcworld", "osz", "osk",
            "pk3", "xmind", "ibooks", "intunewin", "nbu", "obb", "ipsw", "kdz", "ofp", "ozip", "phar", "snap", "wim",
            "esd", "swm", "ppkg", "dmg", "toast", "hfs", "vma", "lpimg", "nsis", "ufp", "3mf-pakket", "mlpackage",
            "sketch", "fig", "graffle", "pages", "numbers", "key-iwork", "procreate", "mogrt", "aep-pakket", "alp",
            "pkg.tar.zst", "tar.md5", "flatpak", "appimage", "run", "exe-installer"}
VMDISKS = {"vhd", "vhdx", "vmdk", "vdi", "qcow", "qcow2", "hdd", "dd", "e01"}
COMICS = {"cbz", "cbr", "cb7", "cbt"}
REPACK = ["zip", "7z", "tar.gz", "txt"]


def sevenzip() -> str | None:
    for name in ("7zz", "7z", "7za", "7zr"):
        p = shutil.which(name)
        if p:
            return p
    for cand in (r"C:\Program Files\7-Zip\7z.exe", "/opt/homebrew/bin/7zz", "/usr/local/bin/7zz"):
        if Path(cand).exists():
            return cand
    return None


def bsdtar() -> str | None:
    import sys
    if sys.platform == "win32":
        return shutil.which("tar")  # Windows 10+: bsdtar
    if sys.platform == "darwin":
        return "/usr/bin/tar"
    return shutil.which("bsdtar")


def targets(fam: str, ext: str) -> list[str]:
    if fam == "compressed":
        return ["uitpakken", "gz", "bz2", "xz", "zst", "zip", "7z"]
    if fam == "comic":
        return [t for t in ("pdf", "cbz", "zip") if t != ext]
    if fam == "vmdisk":
        out = [t for t in ("qcow2", "vmdk", "vdi", "vhdx", "vhd", "raw") if t != ext] if have("qemu-img") else []
        return out + ["zip", "txt"]
    return REPACK


# --------------------------------------------------------------------------- losse compressie

def decompress(src: Path, out_dir: Path) -> Path:
    ext = src.suffix.lower().lstrip(".")
    name = src.stem if src.stem else "bestand"
    data = src.read_bytes()
    try:
        if ext == "gz" or data[:2] == b"\x1f\x8b":
            raw = gzip.decompress(data)
        elif ext == "bz2" or data[:3] == b"BZh":
            raw = bz2.decompress(data)
        elif ext in ("xz", "lzma"):
            raw = lzma.decompress(data)
        elif ext == "zst" or data[:4] == b"\x28\xb5\x2f\xfd":
            import zstandard
            raw = zstandard.ZstdDecompressor().decompressobj().decompress(data)
        elif ext == "lz4":
            import lz4.frame
            raw = lz4.frame.decompress(data)
        elif ext == "br":
            import brotli
            raw = brotli.decompress(data)
        else:
            return _extract_tool(src, out_dir, single=True)
    except ImportError as e:
        raise ConversionError(f".{ext} uitpakken vraagt een extra onderdeel: {e.name}") from e
    except Exception as e:  # noqa: BLE001
        raise ConversionError(f"Uitpakken lukte niet: {e}") from e
    dst = out_dir / name
    dst.write_bytes(raw)
    return dst


def compress(src: Path, out_dir: Path, fmt: str) -> Path:
    data = src.read_bytes()
    dst = out_dir / f"{src.name}.{fmt}"
    if fmt == "gz":
        dst.write_bytes(gzip.compress(data, 9))
    elif fmt == "bz2":
        dst.write_bytes(bz2.compress(data, 9))
    elif fmt == "xz":
        dst.write_bytes(lzma.compress(data, preset=6))
    elif fmt == "zst":
        import zstandard
        dst.write_bytes(zstandard.ZstdCompressor(level=19).compress(data))
    else:
        raise ConversionError(f"Comprimeren als .{fmt} wordt niet ondersteund.")
    return dst


# --------------------------------------------------------------------------- uitpakken

def _ar_extract(src: Path, dest: Path) -> None:
    data = src.read_bytes()
    if data[:8] != b"!<arch>\n":
        raise ConversionError("Geen ar-archief.")
    pos = 8
    while pos + 60 <= len(data):
        name = data[pos:pos + 16].decode("latin-1").strip().rstrip("/")
        size = int(data[pos + 48:pos + 58].decode().strip() or 0)
        body = data[pos + 60:pos + 60 + size]
        if name and name not in ("", "//"):
            out = (dest / Path(name).name)
            out.write_bytes(body)
            if name.startswith(("data.tar", "control.tar")):  # .deb: ook de tar uitpakken
                sub = dest / name.split(".")[0]
                sub.mkdir(exist_ok=True)
                try:
                    if name.endswith(".zst"):
                        import zstandard
                        body = zstandard.ZstdDecompressor().decompressobj().decompress(body)
                        tarfile.open(fileobj=io.BytesIO(body)).extractall(sub, filter="data")
                    else:
                        tarfile.open(fileobj=io.BytesIO(body)).extractall(sub, filter="data")
                    out.unlink()
                except Exception:  # noqa: BLE001
                    pass
        pos += 60 + size + (size % 2)


def _uudecode(src: Path, dest: Path) -> None:
    import binascii
    lines = src.read_text(errors="replace").splitlines()
    out, name = bytearray(), "bestand"
    started = False
    for line in lines:
        if line.startswith("begin "):
            name = line.split(maxsplit=2)[-1].strip()
            started = True
            continue
        if line.strip() == "end":
            break
        if started and line:
            try:
                out += binascii.a2b_uu(line)
            except binascii.Error:
                n = (((ord(line[0]) - 32) & 63) * 4 + 5) // 3
                out += binascii.a2b_uu(line[:n])
    (dest / Path(name).name).write_bytes(bytes(out))


def _extract_tool(src: Path, dest: Path, single: bool = False) -> Path:
    tool = sevenzip()
    if tool:
        r = subprocess.run([tool, "x", "-y", "-bd", f"-o{dest}", "-p-", str(src)], capture_output=True, **NO_WINDOW)
        if r.returncode in (0, 1):
            files = [p for p in dest.rglob("*") if p.is_file()]
            return files[0] if single and len(files) == 1 else dest
        err = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
        if "Wrong password" in err or "encrypted" in err.lower():
            raise ConversionError("Dit archief is met een wachtwoord beveiligd.")
        if not bsdtar():
            raise ConversionError("De inhoud kon niet gelezen worden (leeg, beschadigd of een onbekend "
                                  "bestandssysteem).")
    bt = bsdtar()
    if bt:
        r = subprocess.run([bt, "-xf", str(src), "-C", str(dest)], capture_output=True, **NO_WINDOW)
        if r.returncode == 0:
            files = [p for p in dest.rglob("*") if p.is_file()]
            return files[0] if single and len(files) == 1 else dest
    raise ConversionError("Dit soort archief uitpakken vraagt 7-Zip (zit in de desktop-app; los: 7-zip.org, macOS: "
                          "brew install sevenzip, Linux: sudo apt install 7zip).")


def extract(src: Path, dest: Path) -> Path:
    """Alle inhoud naar de map dest. Geeft dest terug."""
    from .archive import _is_7z, _safe_extract
    dest.mkdir(parents=True, exist_ok=True)
    ext = src.suffix.lower().lstrip(".")
    head = src.read_bytes()[:16] if src.stat().st_size else b""
    if head[:4] == b"Cr24":  # Chrome-extensie: zip met een kop ervoor
        data = src.read_bytes()
        start = data.find(b"PK\x03\x04")
        with zipfile.ZipFile(io.BytesIO(data[start:])) as z:
            z.extractall(dest)
        return dest
    if zipfile.is_zipfile(src) or tarfile.is_tarfile(src) or _is_7z(src):
        if zipfile.is_zipfile(src):
            with zipfile.ZipFile(src) as z:
                if any(i.flag_bits & 1 for i in z.infolist()):
                    raise ConversionError("Dit archief is met een wachtwoord beveiligd.")
        _safe_extract(src, dest)
        return dest
    if head[:8] == b"!<arch>\n":
        _ar_extract(src, dest)
        return dest
    if ext in ("uue", "uu"):
        _uudecode(src, dest)
        return dest
    if ext in ("gz", "bz2", "xz", "zst", "lz4", "br", "lzma"):
        inner = decompress(src, dest)
        if tarfile.is_tarfile(inner):
            sub = dest / "inhoud"
            sub.mkdir(exist_ok=True)
            with tarfile.open(inner) as t:
                t.extractall(sub, filter="data")
            inner.unlink()
        return dest
    if ext in ("tzst", "tar.zst", "pkg.tar.zst"):
        import zstandard
        raw = zstandard.ZstdDecompressor().decompressobj().decompress(src.read_bytes())
        with tarfile.open(fileobj=io.BytesIO(raw)) as t:
            t.extractall(dest, filter="data")
        return dest
    _extract_tool(src, dest)
    return dest


def listing(src: Path) -> str:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="ac-lijst-"))
    try:
        extract(src, tmp)
        rows = sorted((str(p.relative_to(tmp)), p.stat().st_size) for p in tmp.rglob("*") if p.is_file())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    from .util import human_size
    lines = [f"{human_size(s):>10}  {n}" for n, s in rows]
    lines.append(f"\n{len(rows)} bestanden, {human_size(sum(s for _, s in rows))} uitgepakt")
    return "\n".join(lines) + "\n"


def repack(src: Path, out_dir: Path, fmt: str) -> Path:
    from .archive import _pack
    if fmt == "txt":
        dst = out_dir / f"{src.stem}_inhoud.txt"
        dst.write_text(listing(src), encoding="utf-8")
        return dst
    work = out_dir / "_inhoud"
    extract(src, work)
    items = sorted(work.iterdir())
    if not items:
        raise ConversionError("Het archief is leeg.")
    dst = out_dir / f"{src.stem}.{fmt}"
    _pack(items, work, dst, fmt, 9)
    shutil.rmtree(work, ignore_errors=True)
    return dst


# --------------------------------------------------------------------------- stripboeken

def comic(src: Path, out_dir: Path, fmt: str) -> Path:
    work = out_dir / "_strip"
    extract(src, work)
    pages = sorted((p for p in work.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif",
                                                                         ".bmp")),
                   key=lambda p: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)])
    if not pages:
        raise ConversionError("Geen pagina's (afbeeldingen) gevonden in dit stripboek.")
    dst = out_dir / f"{src.stem}.{fmt}"
    if fmt == "pdf":
        from .pdftools import merge
        merge(pages, dst)
    else:
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED) as z:
            for i, p in enumerate(pages, 1):
                z.write(p, f"{i:04d}{p.suffix.lower()}")
    shutil.rmtree(work, ignore_errors=True)
    return dst


# --------------------------------------------------------------------------- VM-schijven

def vmdisk(src: Path, out_dir: Path, fmt: str) -> Path:
    if fmt in ("zip", "txt"):
        return repack(src, out_dir, fmt)
    if not have("qemu-img"):
        raise ConversionError("VM-schijven omzetten vraagt qemu-img (macOS: brew install qemu, Linux: sudo apt install "
                              "qemu-utils, Windows: qemu.org).")
    qfmt = {"vhd": "vpc", "raw": "raw", "qcow2": "qcow2", "vmdk": "vmdk", "vdi": "vdi", "vhdx": "vhdx"}[fmt]
    dst = out_dir / f"{src.stem}.{fmt}"
    r = subprocess.run(["qemu-img", "convert", "-p", "-O", qfmt, str(src), str(dst)], capture_output=True,
                       timeout=4 * 3600, **NO_WINDOW)
    if r.returncode != 0:
        raise ConversionError("qemu-img faalde: " + r.stderr.decode("utf-8", "replace")[-300:])
    return dst


def convert(fam: str, src: Path, out_dir: Path, fmt: str, opts: dict) -> Path:
    if fam == "compressed":
        if fmt == "uitpakken":
            return decompress(src, out_dir)
        if fmt in ("zip", "7z"):
            x = out_dir / "_x"
            x.mkdir(exist_ok=True)
            inner = decompress(src, x)
            from .archive import _pack
            dst = out_dir / f"{inner.name}.{fmt}"
            _pack([inner], inner.parent, dst, fmt, 9)
            return dst
        inner_dir = out_dir / "_x"
        inner_dir.mkdir(exist_ok=True)
        return compress(decompress(src, inner_dir), out_dir, fmt)
    if fam == "comic":
        return comic(src, out_dir, fmt)
    if fam == "vmdisk":
        return vmdisk(src, out_dir, fmt)
    return repack(src, out_dir, fmt)

