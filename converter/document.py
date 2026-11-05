"""Documenten, spreadsheets, presentaties en PDF's (LibreOffice, pandoc, poppler, pikepdf)."""
from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path
from typing import Optional

from . import pdftools
from .util import ConversionError, ProgressFn, have, run, human_size

OFFICE_IN = {"doc", "docx", "odt", "rtf", "xls", "xlsx", "ods", "csv", "tsv", "ppt", "pptx", "odp", "key"}
PANDOC_IN = {"md": "markdown", "markdown": "markdown", "html": "html", "htm": "html", "txt": "markdown",
             "epub": "epub", "tex": "latex", "rst": "rst", "docx": "docx", "odt": "odt"}
PANDOC_OUT = {"md": "gfm", "html": "html", "txt": "plain", "epub": "epub", "docx": "docx", "odt": "odt", "rtf": "rtf"}
LO_FILTER = {"csv": "csv:Text - txt - csv (StarCalc):44,34,76,1", "txt": "txt:Text (encoded):UTF8"}


def _soffice() -> str:
    for name in ("soffice", "libreoffice"):
        if have(name):
            return name
    raise ConversionError("LibreOffice is niet geïnstalleerd; dit soort conversie is niet mogelijk.")


def libreoffice(src: Path, fmt: str, out_dir: Path, infilter: Optional[str] = None) -> Path:
    profile = out_dir / "_lo_profile"
    cmd = [_soffice(), "--headless", "--norestore", f"-env:UserInstallation={profile.resolve().as_uri()}"]
    if infilter:
        cmd.append(f"--infilter={infilter}")
    conv_dir = out_dir / "_lo_out"
    conv_dir.mkdir(exist_ok=True)
    cmd += ["--convert-to", LO_FILTER.get(fmt, fmt), "--outdir", str(conv_dir), str(src)]
    run(cmd, timeout=600)
    shutil.rmtree(profile, ignore_errors=True)
    produced = conv_dir / f"{src.stem}.{fmt}"
    if not produced.exists():
        raise ConversionError(f"LibreOffice kon dit bestand niet naar .{fmt} omzetten.")
    return produced


def pandoc(src: Path, fmt: str, dst: Path, in_fmt: Optional[str] = None) -> Path:
    if not have("pandoc"):
        raise ConversionError("pandoc is niet geïnstalleerd.")
    cmd = ["pandoc", str(src), "-o", str(dst), "-t", PANDOC_OUT[fmt]]
    if in_fmt:
        cmd += ["-f", in_fmt]
    if fmt in ("html", "epub", "docx", "odt", "rtf"):
        cmd.append("--standalone")
    run(cmd, timeout=300)
    return dst


def _final(src: Path, out_dir: Path, fmt: str) -> Path:
    stem = src.stem + ("_bewerkt" if fmt == src.suffix.lstrip(".").lower() else "")
    return out_dir / f"{stem}.{fmt}"


def process(src: Path, out_dir: Path, category: str, opts: dict, progress: Optional[ProgressFn] = None) -> Path:
    ext = src.suffix.lstrip(".").lower()
    fmt = (opts.get("format") or ext).lower()
    dst = _final(src, out_dir, fmt)
    if progress:
        progress(0.1, "Converteren")

    if category == "pdf":
        return _pdf(src, out_dir, fmt, dst, opts, progress)

    # Naar PDF zonder LibreOffice: eenvoudige opmaak via PyMuPDF
    if fmt == "pdf" and ext in pdftools.FALLBACK_IN and not (have("soffice") or have("libreoffice")):
        pdftools.document_to_pdf(src, dst)
        if opts.get("target_bytes") or opts.get("quality") in ("medium", "low"):
            compressed = compress_pdf(dst, out_dir, opts, progress)
            shutil.move(str(compressed), dst)
        return dst

    if opts.get("target_bytes") and fmt != "pdf":
        raise ConversionError("Een doelgrootte kan bij documenten alleen voor PDF-uitvoer. "
                              "Kies PDF, of gebruik 'zip' bij overige bestanden.")

    if category in ("spreadsheet", "presentation"):
        out = libreoffice(src, fmt, out_dir)
    elif fmt in PANDOC_OUT and ext in PANDOC_IN and not (ext in OFFICE_IN and fmt in ("rtf", "txt", "html")):
        out = pandoc(src, fmt, dst, PANDOC_IN[ext])
    elif fmt == "pdf" and ext in PANDOC_IN and ext not in OFFICE_IN:
        tmp = pandoc(src, "docx", out_dir / f"{src.stem}.docx", PANDOC_IN[ext])
        out = libreoffice(tmp, "pdf", out_dir)
    elif ext in OFFICE_IN:
        if fmt in ("md", "epub"):
            tmp = libreoffice(src, "docx", out_dir)
            out = pandoc(tmp, fmt, dst, "docx")
        else:
            out = libreoffice(src, fmt, out_dir)
    else:
        raise ConversionError(f"Conversie van .{ext} naar .{fmt} wordt niet ondersteund.")

    if out != dst:
        shutil.move(str(out), dst)
    if fmt == "pdf" and (opts.get("target_bytes") or opts.get("quality") in ("medium", "low")):
        compressed = compress_pdf(dst, out_dir, opts, progress)
        shutil.move(str(compressed), dst)
    return dst


# --------------------------------------------------------------------------- PDF

def _pdf(src, out_dir, fmt, dst, opts, progress) -> Path:
    if fmt == "pdf":
        out = compress_pdf(src, out_dir, opts, progress)
        shutil.move(str(out), dst)
        return dst
    if fmt in pdftools.PDF_OUT and pdftools.have_pymupdf():
        return pdftools.convert_pdf(src, out_dir, fmt, opts, progress)
    if fmt in ("png", "jpg"):
        if not have("pdftoppm"):
            raise ConversionError("pdftoppm (poppler-utils) is niet geïnstalleerd.")
        pages_dir = out_dir / "_pages"
        pages_dir.mkdir(exist_ok=True)
        dpi = {"high": 200, "medium": 150, "low": 100}.get(opts.get("quality") or "medium", 150)
        run(["pdftoppm", "-r", str(dpi), "-png" if fmt == "png" else "-jpeg", str(src), str(pages_dir / "pagina")],
            timeout=900)
        pages = sorted(pages_dir.iterdir())
        if len(pages) == 1:
            final = out_dir / f"{src.stem}.{fmt}"
            shutil.move(str(pages[0]), final)
            return final
        final = out_dir / f"{src.stem}_paginas.zip"
        with zipfile.ZipFile(final, "w", zipfile.ZIP_DEFLATED) as z:
            for p in pages:
                z.write(p, p.name)
        return final
    if fmt == "txt" and have("pdftotext"):
        run(["pdftotext", "-layout", str(src), str(dst)], timeout=300)
        return dst
    if fmt in ("docx", "odt", "html", "txt"):
        out = libreoffice(src, fmt, out_dir, infilter="writer_pdf_import")
        shutil.move(str(out), dst)
        return dst
    raise ConversionError(f"PDF naar .{fmt} wordt niet ondersteund.")


GS_PRESETS = [("/printer", 300), ("/ebook", 150), ("/screen", 72)]


def compress_pdf(src: Path, out_dir: Path, opts: dict, progress: Optional[ProgressFn] = None) -> Path:
    """Maak een PDF kleiner. Met doelgrootte: probeer steeds sterkere compressie tot het past."""
    target = opts.get("target_bytes")
    quality = opts.get("quality") or "medium"
    original = src.stat().st_size

    # Kandidaten van licht naar zwaar: (dpi, jpeg-kwaliteit)
    steps = [(300, 90), (200, 85), (150, 80), (150, 65), (120, 55), (96, 45), (72, 35), (60, 25)]
    if not target:
        steps = [{"high": (300, 90), "medium": (150, 75), "low": (96, 50)}[quality]]

    best: Optional[Path] = None
    for i, (dpi, q) in enumerate(steps):
        if progress:
            progress(0.1 + 0.85 * i / len(steps), f"Comprimeren ({dpi} dpi)")
        cand = out_dir / f"_pdf_try_{i}.pdf"
        _compress_once(src, cand, dpi, q)
        size = cand.stat().st_size
        if best is None or size < best.stat().st_size:
            best = cand
        if target and size <= target:
            best = cand
            break
        if not target:
            break
    assert best is not None
    if target and best.stat().st_size > target:
        if target > original:
            shutil.copy(src, best)  # groter maken heeft bij PDF geen zin
            return best
        raise ConversionError(f"Kleinst haalbaar is {human_size(best.stat().st_size)}; "
                              f"{human_size(target)} lukt niet (veel tekst/vectoren).")
    if best.stat().st_size >= original and not target:
        shutil.copy(src, best)  # niet groter maken dan het origineel
    return best


def _compress_once(src: Path, dst: Path, dpi: int, quality: int) -> None:
    if have("gs"):
        run(["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5", "-dNOPAUSE", "-dQUIET", "-dBATCH",
             "-dSAFER", "-dDetectDuplicateImages=true", "-dDownsampleColorImages=true",
             "-dDownsampleGrayImages=true", "-dDownsampleMonoImages=true",
             f"-dColorImageResolution={dpi}", f"-dGrayImageResolution={dpi}",
             f"-dMonoImageResolution={max(dpi * 2, 150)}", "-dColorImageDownsampleThreshold=1.0",
             "-dGrayImageDownsampleThreshold=1.0", "-dAutoFilterColorImages=false",
             "-dColorImageFilter=/DCTEncode", "-dAutoFilterGrayImages=false", "-dGrayImageFilter=/DCTEncode",
             f"-dJPEGQ={quality}", f"-sOutputFile={dst}", str(src)], timeout=900)
        return
    _compress_pikepdf(src, dst, dpi, quality)


def _compress_pikepdf(src: Path, dst: Path, dpi: int, quality: int) -> None:
    """Fallback zonder Ghostscript: herschaal en hercomprimeer ingesloten afbeeldingen."""
    try:
        import pikepdf
        from pikepdf import PdfImage
        from PIL import Image
    except ImportError as exc:
        raise ConversionError("Installeer Ghostscript of pikepdf om PDF's te comprimeren.") from exc

    max_side = int(dpi * 11.7)  # ~A4 lange zijde op deze dpi
    with pikepdf.open(src) as pdf:
        seen = set()
        for page in pdf.pages:
            imgs = page.get_images() if hasattr(page, "get_images") else page.images
            for _, raw in imgs.items():
                key = raw.objgen
                if key in seen:
                    continue
                seen.add(key)
                try:
                    pim = PdfImage(raw)
                    if pim.bits_per_component < 8 or "/SMask" in raw or "/Mask" in raw:
                        continue
                    im = pim.as_pil_image()
                except Exception:
                    continue
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                if max(im.size) > max_side:
                    im.thumbnail((max_side, max_side), Image.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=quality, optimize=True)
                if len(buf.getvalue()) >= len(raw.read_raw_bytes()):
                    continue
                raw.write(buf.getvalue(), filter=pikepdf.Name.DCTDecode)
                raw.Width, raw.Height = im.size
                raw.ColorSpace = pikepdf.Name.DeviceRGB if im.mode == "RGB" else pikepdf.Name.DeviceGray
                raw.BitsPerComponent = 8
                for k in ("/DecodeParms", "/Decode"):
                    if k in raw:
                        del raw[k]
        pdf.remove_unreferenced_resources()
        pdf.save(dst, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
