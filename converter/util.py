"""Gedeelde hulpfuncties."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

ProgressFn = Callable[[float, str], None]

# Op Windows geen zwart consolevenster laten flitsen bij elk ffmpeg/LibreOffice-commando.
NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


class ConversionError(Exception):
    """Fout die aan de gebruiker getoond mag worden."""


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def run(cmd: list[str], timeout: Optional[int] = None, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Voer een commando uit zonder shell; gooi ConversionError bij een fout."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, cwd=cwd, **NO_WINDOW)
    except FileNotFoundError as exc:
        raise ConversionError(f"Program not found: {cmd[0]}. Is it installed?") from exc
    except subprocess.TimeoutExpired as exc:
        raise ConversionError(f"{cmd[0]} took too long and was stopped.") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-6:]
        raise ConversionError(f"{Path(cmd[0]).name} faalde:\n" + "\n".join(tail))
    return proc


_UNITS = {"b": 1, "kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3}


def parse_size(value, unit: str = "mb") -> int:
    """Zet bijv. (2.5, 'MB') of '800 KB' om naar bytes."""
    if isinstance(value, str):
        m = re.fullmatch(r"\s*([\d.,]+)\s*([kmg]?b)?\s*", value.lower())
        if not m:
            raise ConversionError(f"Invalid size: {value!r}")
        value = float(m.group(1).replace(",", "."))
        unit = m.group(2) or unit
    unit = (unit or "mb").lower()
    if unit not in _UNITS:
        raise ConversionError(f"Onbekende eenheid: {unit}")
    size = int(float(value) * _UNITS[unit])
    if size <= 0:
        raise ConversionError("Target size must be greater than 0.")
    return size


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} GB"


def parse_time(value) -> Optional[float]:
    """'1:23.5', '00:01:23', '83.5' -> seconden. Leeg -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    value = str(value).strip().replace(",", ".")
    if not value:
        return None
    parts = value.split(":")
    if len(parts) > 3:
        raise ConversionError(f"Ongeldige tijd: {value}")
    try:
        total = 0.0
        for p in parts:
            total = total * 60 + float(p)
    except ValueError as exc:
        raise ConversionError(f"Ongeldige tijd: {value}") from exc
    if total < 0:
        raise ConversionError("Time cannot be negative.")
    return total


def ffprobe(path: Path) -> dict:
    proc = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    return json.loads(proc.stdout or "{}")
