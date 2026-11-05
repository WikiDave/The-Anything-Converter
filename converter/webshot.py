"""Website opslaan als PDF, PNG of JPG met een geïnstalleerde Chrome/Edge/Chromium (headless)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

from .util import NO_WINDOW, ConversionError


def no_sandbox() -> list[str]:
    """Chrome weigert als root te starten met sandbox (bijv. in een container)."""
    return ["--no-sandbox"] if hasattr(os, "geteuid") and os.geteuid() == 0 else []


def chromium() -> Optional[str]:
    if sys.platform == "win32":
        cands = [Path(os.environ.get(v, "")) / sub for v in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")
                 for sub in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe")]
    elif sys.platform == "darwin":
        cands = [Path(f"/Applications/{a}.app/Contents/MacOS/{a}")
                 for a in ("Google Chrome", "Microsoft Edge", "Chromium", "Brave Browser")]
    else:
        cands = [shutil.which(n) for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                                            "microsoft-edge", "brave-browser")]
    for c in cands:
        if c and os.path.isfile(c):
            return str(c)
    return None


def capture(url: str, out_dir: Path, fmt: str, progress: Optional[Callable[[float, str], None]] = None) -> Path:
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    exe = chromium()
    if not exe:
        raise ConversionError("Hiervoor is Chrome, Edge of Chromium nodig (gratis te installeren).")
    name = re.sub(r"[^A-Za-z0-9.-]+", "_", re.sub(r"^https?://(www\.)?", "", url))[:60].strip("_") or "website"
    dst = out_dir / f"{name}.{fmt}"
    profile = tempfile.mkdtemp(prefix="webshot-")
    base = [exe, "--headless=new", "--disable-gpu", *no_sandbox(), "--hide-scrollbars", "--no-first-run",
            f"--user-data-dir={profile}", "--virtual-time-budget=8000"]
    if progress:
        progress(0.3, "pagina laden")
    if fmt == "pdf":
        cmd = [*base, "--no-pdf-header-footer", f"--print-to-pdf={dst}", url]
        target = dst
    else:
        target = dst.with_suffix(".png")
        cmd = [*base, "--window-size=1366,2400", f"--screenshot={target}", url]
    try:
        subprocess.run(cmd, capture_output=True, timeout=120, **NO_WINDOW)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not target.exists():
        raise ConversionError("De website kon niet geladen worden.")
    if fmt == "jpg":
        from PIL import Image
        Image.open(target).convert("RGB").save(dst, "JPEG", quality=88)
        target.unlink()
    return dst
