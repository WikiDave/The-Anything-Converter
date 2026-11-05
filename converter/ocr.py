"""Tekstherkenning (OCR) met wat het systeem al heeft.

- macOS: Apple Vision (ingebouwd, alle talen van macOS)
- Windows: Windows.Media.Ocr (ingebouwd, de talen van Windows)
- overal: Tesseract, als het geïnstalleerd is (Linux: sudo apt install tesseract-ocr tesseract-ocr-eng)
"""
from __future__ import annotations

import shutil
import subprocess
import os
import sys
import tempfile
from pathlib import Path

from .util import NO_WINDOW, ConversionError

PREFERRED_LANGS = ["eng", "nld", "deu", "fra", "spa", "ita", "por", "rus", "tur", "ara", "chi_sim", "jpn"]


def engine() -> str | None:
    if sys.platform == "darwin":
        try:
            import Vision  # noqa: F401
            return "vision"
        except ImportError:
            pass
    if sys.platform == "win32":
        try:
            from winrt.windows.media.ocr import OcrEngine
            if OcrEngine.try_create_from_user_profile_languages() is not None:
                return "windows"
        except Exception:  # noqa: BLE001
            pass
    if shutil.which("tesseract"):
        return "tesseract"
    return None


def available() -> bool:
    return engine() is not None


def missing_message() -> str:
    if sys.platform.startswith("linux"):
        return ("No OCR found. Install Tesseract: sudo apt install tesseract-ocr tesseract-ocr-eng (Fedora: sudo dnf install tesseract tesseract-langpack-eng).")
    if sys.platform == "win32":
        return ("Windows text recognition is not available. Add a language with 'Optical character recognition' via Settings → Time & language → Language, or install Tesseract.")
    return "No OCR available on this system."


def image(path: Path) -> str:
    """Tekst uit een afbeeldingsbestand."""
    kind = engine()
    if kind is None:
        raise ConversionError(missing_message())
    path = _normalise(Path(path))
    if kind == "vision":
        return _vision(path)
    if kind == "windows":
        return _windows(path)
    return _tesseract(path)


def image_bytes(data: bytes, suffix: str = ".png") -> str:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / ("ocr" + suffix)
        p.write_bytes(data)
        return image(p)


def _normalise(path: Path) -> Path:
    """HEIC, WebP, enz. eerst naar PNG; heel grote beelden verkleinen (Windows-OCR heeft een maximum)."""
    from PIL import ImageOps
    from .image import _open_any
    try:
        with _open_any(path, Path(tempfile.mkdtemp(prefix="ocr-"))) as im:
            im = ImageOps.exif_transpose(im)
            limit = 4000 if engine() == "windows" else 8000
            change = path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp") \
                or max(im.size) > limit or im.mode not in ("RGB", "L")
            if not change:
                return path
            if max(im.size) > limit:
                im.thumbnail((limit, limit))
            out = Path(tempfile.mkdtemp(prefix="ocr-")) / "image.png"
            im.convert("RGB").save(out)
            return out
    except Exception as e:  # noqa: BLE001
        raise ConversionError(f"Image cannot be read: {e}") from e


def _vision(path: Path) -> str:
    import Vision
    from Foundation import NSURL
    url = NSURL.fileURLWithPath_(str(path))
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(True)
    if hasattr(req, "setAutomaticallyDetectsLanguage_"):
        req.setAutomaticallyDetectsLanguage_(True)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise ConversionError(f"Text recognition failed: {err}")
    lines = []
    for obs in req.results() or []:
        cand = obs.topCandidates_(1)
        if cand:
            box = obs.boundingBox()
            lines.append((-(box.origin.y + box.size.height), box.origin.x, cand[0].string()))
    return _join(lines)


def _join(lines) -> str:
    """Regels op volgorde (boven naar onder, links naar rechts); regels op dezelfde hoogte samen."""
    lines.sort()
    out, last_y, cur = [], None, []
    for y, x, text in lines:
        if last_y is not None and abs(y - last_y) > 0.012:
            out.append("  ".join(cur))
            cur = []
        cur.append(text)
        last_y = y
    if cur:
        out.append("  ".join(cur))
    return "\n".join(out)


def _windows(path: Path) -> str:
    import asyncio

    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage import FileAccessMode, StorageFile

    async def go():
        f = await StorageFile.get_file_from_path_async(str(path.resolve()))
        stream = await f.open_async(FileAccessMode.READ)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        eng = OcrEngine.try_create_from_user_profile_languages()
        result = await eng.recognize_async(bitmap)
        return "\n".join(line.text for line in result.lines)

    return asyncio.run(go())


def _tesseract_langs() -> str:
    try:
        out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=20,
                             **NO_WINDOW).stdout
    except Exception:  # noqa: BLE001
        return "eng"
    have = {ln.strip() for ln in out.splitlines()[1:]}
    langs = [lang for lang in PREFERRED_LANGS if lang in have][:4]
    return "+".join(langs) or "eng"


def _tesseract(path: Path) -> str:
    r = subprocess.run(["tesseract", str(path), "stdout", "-l", _tesseract_langs()], capture_output=True,
                       timeout=600, **NO_WINDOW)
    if r.returncode != 0:
        raise ConversionError("Tesseract failed: " + r.stderr.decode("utf-8", "replace")[-300:])
    return r.stdout.decode("utf-8", "replace").strip()


def searchable_pdf_text(path: Path, progress=None) -> str:
    """Tekst uit een (gescande) PDF: tekstlaag waar die er is, OCR op pagina's zonder tekst."""
    from .pdftools import _fitz, page_text
    doc = _fitz().open(path)
    parts = []
    for i, page in enumerate(doc):
        parts.append(page_text(page).rstrip())
        if progress:
            progress(0.1 + 0.85 * (i + 1) / len(doc), f"page {i + 1}/{len(doc)}")
    return "\n\n".join(parts).strip()


def capture_screen() -> Path:
    """Laat de gebruiker een stuk van het scherm kiezen; geeft het pad naar de schermafbeelding."""
    if (os.environ.get("SSH_CONNECTION") or os.path.exists("/.dockerenv")) and sys.platform.startswith("linux") \
            and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        raise ConversionError("A screenshot is not possible over SSH or in Docker (no screen here). Save a "
                              "screenshot as an image file and recognise the text from that file.")
    out = Path(tempfile.mkdtemp(prefix="screenshot-")) / "screen.png"
    if sys.platform == "darwin":
        subprocess.run(["screencapture", "-i", "-x", str(out)], timeout=300)
    elif sys.platform == "win32":
        return _capture_windows(out)
    else:
        for cmd in (["gnome-screenshot", "-a", "-f", str(out)], ["spectacle", "-r", "-b", "-n", "-o", str(out)],
                    ["xfce4-screenshooter", "-r", "-s", str(out)], ["flameshot", "gui", "-p", str(out)],
                    ["scrot", "-s", str(out)], ["import", str(out)]):
            if shutil.which(cmd[0]):
                subprocess.run(cmd, timeout=300)
                break
        else:
            if shutil.which("grim") and shutil.which("slurp"):
                region = subprocess.run(["slurp"], capture_output=True, text=True, timeout=300).stdout.strip()
                if region:
                    subprocess.run(["grim", "-g", region, str(out)], timeout=60)
            else:
                raise ConversionError("No screenshot program found (e.g. gnome-screenshot). Take a screenshot yourself and paste it with Ctrl+V.")
    if not out.exists() or out.stat().st_size == 0:
        raise ConversionError("No screenshot taken (cancelled).")
    return out


def _capture_windows(out: Path) -> Path:
    """Windows: knipprogramma openen (Win+Shift+S) en het resultaat van het klembord halen."""
    import os
    import time

    from PIL import Image, ImageGrab
    before = ImageGrab.grabclipboard()
    before_sig = before.tobytes()[:4096] if isinstance(before, Image.Image) else None
    os.startfile("ms-screenclip:")  # noqa: S606 - Windows-knipprogramma
    deadline = time.time() + 120
    while time.time() < deadline:
        time.sleep(0.5)
        im = ImageGrab.grabclipboard()
        if isinstance(im, Image.Image) and im.tobytes()[:4096] != before_sig:
            im.save(out)
            return out
    raise ConversionError("No screenshot received (within 2 minutes).")

