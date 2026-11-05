"""Archieven en overige bestanden: inpakken, omzetten tussen archiefformaten, comprimeren."""
from __future__ import annotations

import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Optional

from .detect import extension
from .util import ConversionError, ProgressFn, human_size

TAR_MODES = {"tar": "w", "tar.gz": "w:gz", "tar.bz2": "w:bz2", "tar.xz": "w:xz"}


def _is_7z(src: Path) -> bool:
    try:
        with open(src, "rb") as f:
            return f.read(6) == b"7z\xbc\xaf\x27\x1c"
    except OSError:
        return False


def _py7zr():
    try:
        import py7zr
    except ImportError as e:
        raise ConversionError("7z support is missing (pip install py7zr).") from e
    return py7zr


def _is_archive(src: Path) -> bool:
    return zipfile.is_zipfile(src) or tarfile.is_tarfile(src) or _is_7z(src)


def _safe_extract(src: Path, dest: Path) -> None:
    dest = dest.resolve()
    if _is_7z(src):
        with _py7zr().SevenZipFile(src) as z:
            for name in z.getnames():
                if not (dest / name).resolve().is_relative_to(dest):
                    raise ConversionError("Archief bevat onveilige paden.")
            z.extractall(dest)
        return
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            for m in z.infolist():
                target = (dest / m.filename).resolve()
                if not target.is_relative_to(dest):
                    raise ConversionError("Archief bevat onveilige paden.")
            z.extractall(dest)
    else:
        with tarfile.open(src) as t:
            t.extractall(dest, filter="data")


def _pack(items: list[Path], base: Path, dst: Path, fmt: str, level: int) -> None:
    if fmt == "zip":
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=level, strict_timestamps=False) as z:
            for item in items:
                if item.is_dir():
                    for f in sorted(item.rglob("*")):
                        z.write(f, f.relative_to(base))
                else:
                    z.write(item, item.relative_to(base))
    elif fmt == "7z":
        filters = [{"id": _py7zr().FILTER_LZMA2, "preset": min(9, level)}]
        with _py7zr().SevenZipFile(dst, "w", filters=filters) as z:
            for item in items:
                if item.is_dir():
                    z.writeall(item, str(item.relative_to(base)))
                else:
                    z.write(item, str(item.relative_to(base)))
    elif fmt in TAR_MODES:
        kw = {} if fmt == "tar" else ({"preset": level} if fmt == "tar.xz" else {"compresslevel": max(level, 1)})
        with tarfile.open(dst, TAR_MODES[fmt], **kw) as t:
            for item in items:
                t.add(item, arcname=str(item.relative_to(base)))
    else:
        raise ConversionError(f"Archive format .{fmt} is not supported.")


def process(src: Path, out_dir: Path, opts: dict, progress: Optional[ProgressFn] = None) -> Path:
    fmt = (opts.get("format") or "zip").lower()
    level = {"high": 6, "medium": 9, "low": 9}.get(opts.get("quality") or "medium", 9)
    src_ext = extension(src)
    stem = src.name[: -(len(src_ext) + 1)] if src_ext else src.name
    if progress:
        progress(0.1, "Packing")

    if _is_archive(src) and src_ext in ("zip", "7z", "tar", "tar.gz", "tar.bz2", "tar.xz", "tgz", "gz", "bz2", "xz"):
        work = out_dir / "_extract"
        work.mkdir(exist_ok=True)
        _safe_extract(src, work)
        items = sorted(work.iterdir())
        base = work
        name = stem.removesuffix(".tar")
    else:
        items = [src]
        base = src.parent
        name = src.name

    dst = out_dir / f"{name}.{fmt}"
    if dst.resolve() == src.resolve():
        dst = out_dir / f"{name}_bewerkt.{fmt}"
    _pack(items, base, dst, fmt, level)

    # Bij een doelgrootte: probeer sterkere compressie voordat we opgeven.
    target = opts.get("target_bytes")
    if target and dst.stat().st_size > target:
        for alt in ("7z", "tar.xz"):
            if fmt != alt:
                cand = out_dir / f"{name}.{alt}"
                _pack(items, base, cand, alt, 9)
                if cand.stat().st_size <= target:
                    dst.unlink()
                    return cand
                cand.unlink()
        raise ConversionError(
            f"Lossless packing reaches {human_size(dst.stat().st_size)}, not {human_size(target)}. This file type is already compressed; only media/PDFs can be made smaller.")
    shutil.rmtree(out_dir / "_extract", ignore_errors=True)
    return dst
