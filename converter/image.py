"""Afbeeldingen: converteren, schalen en naar een doelgrootte brengen (kleiner of groter)."""
from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps, ImageSequence

from .util import ConversionError, ProgressFn, have, run, human_size

LOSSY = {"jpg", "webp", "avif"}
PIL_FORMAT = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "avif": "AVIF", "gif": "GIF",
              "bmp": "BMP", "tiff": "TIFF", "ico": "ICO", "pdf": "PDF"}
QUALITY = {"high": 92, "medium": 82, "low": 65}
MAX_PIXELS = 20000  # maximale breedte/hoogte bij vergroten

Image.MAX_IMAGE_PIXELS = 400_000_000


def _load(src: Path, work: Path) -> list[Image.Image]:
    """Laad alle frames. Valt terug op ImageMagick voor exotische formaten (heic, svg, psd...)."""
    try:
        im = Image.open(src)
        im.load()
    except Exception:
        try:
            import pillow_heif  # type: ignore
            pillow_heif.register_heif_opener()
            im = Image.open(src)
            im.load()
        except Exception:
            magick = "magick" if have("magick") else "convert"
            if not have(magick):
                raise ConversionError("Dit afbeeldingsformaat kan niet gelezen worden (ImageMagick ontbreekt).")
            tmp = work / "_tmp_input.png"
            run([magick, f"{src}[0]", str(tmp)], timeout=300)
            im = Image.open(tmp)
            im.load()
    frames = [ImageOps.exif_transpose(f.copy()) for f in ImageSequence.Iterator(im)]
    for f, orig in zip(frames, ImageSequence.Iterator(im)):
        f.info["duration"] = orig.info.get("duration", 100)
    return frames


def _prepare(frame: Image.Image, fmt: str) -> Image.Image:
    has_alpha = frame.mode in ("RGBA", "LA") or (frame.mode == "P" and "transparency" in frame.info)
    if fmt in ("jpg", "pdf", "bmp") or (fmt == "avif" and not has_alpha):
        if has_alpha:
            frame = frame.convert("RGBA")
            bg = Image.new("RGB", frame.size, (255, 255, 255))
            bg.paste(frame, mask=frame.split()[-1])
            return bg
        return frame.convert("RGB")
    if frame.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        return frame.convert("RGBA" if has_alpha else "RGB")
    return frame


def _encode(frames: list[Image.Image], fmt: str, scale: float, quality: int,
            palette: bool = False) -> bytes:
    out = []
    for f in frames:
        if abs(scale - 1) > 1e-3:
            w = max(1, round(f.width * scale))
            h = max(1, round(f.height * scale))
            f = f.resize((w, h), Image.LANCZOS)
        f = _prepare(f, fmt)
        if palette and fmt == "png":
            f = f.convert("RGBA").quantize(256, method=Image.Quantize.FASTOCTREE)
        out.append(f)
    buf = io.BytesIO()
    kw: dict = {}
    if fmt in LOSSY:
        kw["quality"] = int(quality)
    if fmt == "jpg":
        kw.update(optimize=True, progressive=True, subsampling=0 if quality >= 90 else 2)
    if fmt == "png":
        kw["optimize"] = True
    if fmt == "webp":
        kw["method"] = 4
    if fmt == "tiff":
        kw["compression"] = "tiff_lzw"
    if fmt == "ico":
        side = min(256, max(out[0].size))
        kw["sizes"] = [(s, s) for s in (16, 32, 48, 64, 128, 256) if s <= side] or [(side, side)]
    multi = len(out) > 1 and fmt in ("gif", "webp", "tiff", "pdf")
    if multi:
        kw.update(save_all=True, append_images=out[1:])
        if fmt in ("gif", "webp"):
            kw.update(loop=0, duration=[f.info.get("duration", 100) for f in frames])
    out[0].save(buf, PIL_FORMAT[fmt], **kw)
    return buf.getvalue()


def _fit_lossy(frames, fmt, target, progress) -> bytes:
    """Zoek de hoogste kwaliteit (en zo nodig schaal) die onder de doelgrootte blijft."""
    best: Optional[bytes] = None
    scale = 1.0
    first = _encode(frames, fmt, 1.0, 95)
    if len(first) < target:
        # Groter maken: eerst kwaliteit 100, daarna opschalen.
        data = _encode(frames, fmt, 1.0, 100)
        if len(data) >= target * 0.9:
            return data if len(data) <= target else first
        return _grow(frames, fmt, target, 100, data, progress)

    for rnd in range(8):
        if progress:
            progress(min(0.1 + rnd * 0.1, 0.9), "Kwaliteit zoeken")
        lo, hi = 5, 95
        small = _encode(frames, fmt, scale, lo)
        if len(small) > target:
            scale *= math.sqrt(target / len(small)) * 0.95
            if min(f.width for f in frames) * scale < 8:
                break
            continue
        best = small
        while lo <= hi:
            mid = (lo + hi) // 2
            data = _encode(frames, fmt, scale, mid)
            if len(data) <= target:
                best, lo = data, mid + 1
            else:
                hi = mid - 1
        return best
    raise ConversionError(f"Kon niet kleiner dan {human_size(target)} komen.")


def _fit_lossless(frames, fmt, target, progress) -> bytes:
    data = _encode(frames, fmt, 1.0, 100)
    if len(data) < target * 0.9:
        return _grow(frames, fmt, target, 100, data, progress)
    if len(data) <= target:
        return data
    palette = False
    if fmt == "png":
        pal = _encode(frames, fmt, 1.0, 100, palette=True)
        if len(pal) <= target:
            return pal
        palette, data = True, pal
    scale = 1.0
    for rnd in range(12):
        if progress:
            progress(min(0.1 + rnd * 0.07, 0.9), "Schaal zoeken")
        scale *= math.sqrt(target / len(data)) * 0.97
        data = _encode(frames, fmt, scale, 100, palette)
        if len(data) <= target:
            return data
    raise ConversionError(f"Kon niet kleiner dan {human_size(target)} komen.")


def _grow(frames, fmt, target, quality, data, progress) -> bytes:
    """Vergroot de resolutie tot de bestandsgrootte de doelgrootte benadert."""
    best = data
    scale = 1.0
    max_scale = MAX_PIXELS / max(max(f.size) for f in frames)
    for rnd in range(10):
        if progress:
            progress(min(0.1 + rnd * 0.08, 0.9), "Vergroten")
        ratio = target / len(data)
        if 0.97 <= ratio <= 1.0:
            break
        scale = min(scale * math.sqrt(ratio) * (0.99 if ratio < 1 else 1.0), max_scale)
        data = _encode(frames, fmt, scale, quality)
        if len(data) <= target and len(data) > len(best):
            best = data
        if scale >= max_scale and len(data) < target:
            break
    return best


def process(src: Path, out_dir: Path, opts: dict, progress: Optional[ProgressFn] = None) -> Path:
    fmt = (opts.get("format") or src.suffix.lstrip(".")).lower()
    fmt = {"jpeg": "jpg", "tif": "tiff", "jfif": "jpg"}.get(fmt, fmt)
    if fmt not in PIL_FORMAT:
        raise ConversionError(f"Uitvoerformaat .{fmt} wordt niet ondersteund voor afbeeldingen.")

    frames = _load(src, out_dir)
    if progress:
        progress(0.05, "Afbeelding geladen")

    # Handmatig schalen
    if opts.get("scale_percent"):
        pct = float(opts["scale_percent"]) / 100
        frames = [f.resize((max(1, round(f.width * pct)), max(1, round(f.height * pct))), Image.LANCZOS)
                  for f in frames]
    elif opts.get("width") or opts.get("height"):
        w0, h0 = frames[0].size
        w = int(opts["width"]) if opts.get("width") else None
        h = int(opts["height"]) if opts.get("height") else None
        if w and not h:
            h = round(h0 * w / w0)
        if h and not w:
            w = round(w0 * h / h0)
        frames = [f.resize((w, h), Image.LANCZOS) for f in frames]

    target = opts.get("target_bytes")
    quality = QUALITY.get(opts.get("quality") or "high", 92)
    if target and fmt in ("ico", "pdf"):
        raise ConversionError(f"Doelgrootte wordt niet ondersteund voor .{fmt}; kies bijv. jpg, png of webp.")
    if target:
        data = (_fit_lossy if fmt in LOSSY else _fit_lossless)(frames, fmt, target, progress)
    else:
        data = _encode(frames, fmt, 1.0, quality)

    stem = src.stem + ("_bewerkt" if fmt == src.suffix.lstrip(".").lower() else "")
    dst = out_dir / f"{stem}.{fmt}"
    dst.write_bytes(data)
    return dst
