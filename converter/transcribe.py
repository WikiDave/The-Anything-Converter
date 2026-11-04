"""Audio en video naar tekst (spraakherkenning met whisper.cpp via pywhispercpp), volledig lokaal.

Het taalmodel wordt de eerste keer gedownload (base: ~150 MB, small: ~480 MB) en daarna bewaard.
Uitvoer: .txt (lopende tekst), .srt of .vtt (ondertitels met tijden).
"""
from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from .util import NO_WINDOW, ConversionError, ffprobe

ProgressFn = Callable[[float, str], None]
MODELS = {"tiny": 77_691_713, "base": 147_951_465, "small": 487_601_967, "medium": 1_533_763_059}
URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{}.bin"
TEXT_FORMATS = ("txt", "srt", "vtt")


def model_dir() -> Path:
    if os.environ.get("CONVERTER_MODELS"):
        root = Path(os.environ["CONVERTER_MODELS"])
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AnythingConverter" / "modellen"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "AnythingConverter" / "modellen"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "AnythingConverter" / "modellen"
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_model(name: str, progress: Optional[ProgressFn] = None, cancelled=lambda: False) -> Path:
    if name not in MODELS:
        raise ConversionError(f"Onbekend spraakmodel: {name}")
    path = model_dir() / f"ggml-{name}.bin"
    if path.exists() and path.stat().st_size > MODELS[name] * 0.9:
        return path
    part = path.with_suffix(".part")
    try:
        with urllib.request.urlopen(URL.format(name), timeout=60) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or MODELS[name])
            done = 0
            while True:
                if cancelled():
                    raise ConversionError("Gestopt.")
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(0.02 + 0.28 * done / total,
                             f"spraakmodel '{name}' downloaden (eenmalig) {done >> 20}/{total >> 20} MB")
    except ConversionError:
        part.unlink(missing_ok=True)
        raise
    except Exception as e:  # noqa: BLE001
        part.unlink(missing_ok=True)
        raise ConversionError(f"Spraakmodel downloaden mislukt (internet nodig, alleen de eerste keer): {e}") from e
    part.replace(path)
    return path


def _audio(src: Path, start: float = 0.0, end: Optional[float] = None):
    import numpy as np
    cmd = ["ffmpeg", "-nostdin", "-v", "error"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(src)]
    if end is not None:
        cmd += ["-t", f"{end - start:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    r = subprocess.run(cmd, capture_output=True, **NO_WINDOW)
    if r.returncode != 0 or not r.stdout:
        raise ConversionError("Geen geluid gevonden in dit bestand. " + r.stderr.decode("utf-8", "replace")[-200:])
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0


def _stamp(cs: int, sep: str) -> str:
    ms = int(cs) * 10
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def write(segments, dst: Path, fmt: str, offset_cs: int = 0) -> None:
    segs = [(s.t0 + offset_cs, s.t1 + offset_cs, s.text.strip()) for s in segments if s.text.strip()]
    if fmt == "txt":
        text, line = [], ""
        for _, _, t in segs:  # zinnen samenvoegen tot alinea's
            line = (line + " " + t).strip()
            if line.endswith((".", "?", "!")) and len(line) > 300:
                text.append(line)
                line = ""
        if line:
            text.append(line)
        dst.write_text("\n\n".join(text) + "\n", encoding="utf-8")
    elif fmt == "srt":
        dst.write_text("\n".join(f"{i}\n{_stamp(a, ',')} --> {_stamp(b, ',')}\n{t}\n"
                                 for i, (a, b, t) in enumerate(segs, 1)), encoding="utf-8")
    else:
        dst.write_text("WEBVTT\n\n" + "\n".join(f"{_stamp(a, '.')} --> {_stamp(b, '.')}\n{t}\n"
                                                for a, b, t in segs), encoding="utf-8")


def transcribe(src: Path, dst: Path, fmt: str, opts: dict, progress: Optional[ProgressFn] = None,
               start: float = 0.0, end: Optional[float] = None) -> Path:
    cancelled = opts.get("_cancelled") or (lambda: False)
    try:
        from pywhispercpp.model import Model
    except ImportError as e:
        raise ConversionError("Spraakherkenning ontbreekt (pip install pywhispercpp).") from e
    name = opts.get("speech_model") or "base"
    model_path = ensure_model(name, progress, cancelled)
    if progress:
        progress(0.32, "geluid voorbereiden")
    audio = _audio(src, start, end)
    total_cs = max(1, int(len(audio) / 16000 * 100))
    lang = (opts.get("language") or "auto").lower()

    def on_segment(seg):
        if progress:
            progress(0.35 + 0.6 * min(1.0, seg.t1 / total_cs), f"herkennen {_stamp(seg.t1, ',')[:8]}: {seg.text.strip()[:60]}")

    if progress:
        progress(0.35, f"spraak herkennen (model {name})")
    threads = max(1, min(8, (os.cpu_count() or 4)))
    try:
        model = Model(str(model_path), redirect_whispercpp_logs_to=None, print_progress=False, print_realtime=False,
                      n_threads=threads)
    except TypeError:  # oudere pywhispercpp (bijv. op Intel-Macs)
        model = Model(str(model_path), print_progress=False, print_realtime=False, n_threads=threads)
    kw = dict(language=lang, translate=bool(opts.get("translate")), new_segment_callback=on_segment)
    try:
        segments = model.transcribe(audio, abort_callback=cancelled, **kw)
    except TypeError:
        segments = model.transcribe(audio, **kw)
    if cancelled():
        raise ConversionError("Gestopt.")
    if not any(s.text.strip() for s in segments):
        raise ConversionError("Er is geen spraak herkend in dit bestand.")
    write(segments, dst, fmt, int(start * 100))
    return dst


def duration(src: Path) -> float:
    try:
        return float(ffprobe(src).get("format", {}).get("duration") or 0)
    except ConversionError:
        return 0.0
