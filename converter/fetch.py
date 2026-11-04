"""Video's ophalen via een link (YouTube en vele andere sites) met yt-dlp.

Alleen bedoeld voor eigen video's, video's met een vrije licentie (bijv. Creative Commons)
of video's waarvoor je toestemming hebt.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .util import ConversionError, ProgressFn

MAX_DURATION = 4 * 3600  # langer dan 4 uur weigeren we


def _check_url(url: str) -> str:
    url = (url or "").strip()
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ConversionError("Plak een volledige link die begint met https://")
    return url


def _friendly(msg: str) -> str:
    m = msg.lower()
    rules = [
        ("private video", "Deze video is privé."),
        ("sign in to confirm your age", "Deze video heeft een leeftijdsgrens en vereist inloggen; dat wordt niet ondersteund."),
        ("sign in to confirm you", "YouTube vraagt om in te loggen (bot-controle). Probeer het later opnieuw of werk yt-dlp bij."),
        ("video unavailable", "Deze video is niet beschikbaar."),
        ("is not available in your country", "Deze video is niet beschikbaar in jouw land."),
        ("members-only", "Deze video is alleen voor kanaalleden."),
        ("unsupported url", "Deze link wordt niet ondersteund."),
        ("live event", "Livestreams kunnen niet gedownload worden."),
        ("requested format is not available", "Er is geen downloadbare versie gevonden."),
        ("http error 403", "De site weigert de download (403). Werk yt-dlp bij: pip install -U yt-dlp"),
        ("no supported javascript runtime", "yt-dlp heeft een JavaScript-runtime nodig voor YouTube. Installeer Deno of Node.js."),
    ]
    for key, text in rules:
        if key in m:
            return text
    tail = re.sub(r"\x1b\[[0-9;]*m", "", msg).strip().splitlines()[-1:] or [msg]
    return "Downloaden mislukt: " + tail[0].replace("ERROR: ", "")


class _QuietLogger:
    """yt-dlp zonder uitvoer in de terminal; fouten komen via DownloadError bij de gebruiker."""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def download(url: str, out_dir: Path, audio_only: bool = False, progress: Optional[ProgressFn] = None) -> Path:
    try:
        import yt_dlp
    except ImportError as exc:
        raise ConversionError("yt-dlp is niet geïnstalleerd. Voer uit: pip install -U \"yt-dlp[default]\"") from exc
    url = _check_url(url)
    out_dir.mkdir(parents=True, exist_ok=True)

    def hook(d: dict) -> None:
        if not progress:
            return
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            frac = done / total if total else 0
            # bij video+audio komen er twee downloads achter elkaar; samen 0-95%
            part = hook.part
            progress(min(0.95, (part + frac) / hook.parts * 0.95), "Downloaden")
        elif d.get("status") == "finished":
            hook.part = min(hook.part + 1, hook.parts - 1)
            progress(min(0.95, hook.part / hook.parts * 0.95), "Samenvoegen")
    hook.part, hook.parts = 0, 1 if audio_only else 2

    opts = {
        "outtmpl": str(out_dir / "%(title).80B.%(ext)s"),
        "restrictfilenames": True,
        "windowsfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [hook],
        "ffmpeg_location": shutil.which("ffmpeg") or None,
        "logger": _QuietLogger(),
    }
    if audio_only:
        opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
    else:
        # Liefst mp4 (H.264 + AAC) zodat het overal afspeelt en de preview werkt.
        opts["format"] = ("bv*[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/bv*[ext=mp4]+ba[ext=m4a]/"
                          "b[ext=mp4]/bv*+ba/b")
        opts["merge_output_format"] = "mp4"

    if progress:
        progress(0.01, "Link controleren")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise ConversionError("Deze link kon niet gedownload worden.")
            if info.get("_type") == "playlist":
                raise ConversionError("Dit is een afspeellijst; plak de link van één video.")
            if info.get("is_live"):
                raise ConversionError("Livestreams kunnen niet gedownload worden.")
            if (info.get("duration") or 0) > MAX_DURATION:
                raise ConversionError(f"Deze video is langer dan {MAX_DURATION // 3600} uur.")
            if progress:
                progress(0.03, "Downloaden")
            info = ydl.process_ie_result(info, download=True)
            path = Path(info.get("requested_downloads", [{}])[0].get("filepath") or ydl.prepare_filename(info))
    except yt_dlp.utils.DownloadError as exc:
        raise ConversionError(_friendly(str(exc))) from exc
    if not path.exists():
        files = sorted((f for f in out_dir.iterdir() if f.is_file()), key=lambda f: f.stat().st_size, reverse=True)
        if not files:
            raise ConversionError("Downloaden mislukt: geen bestand ontvangen.")
        path = files[0]
    if progress:
        progress(0.99, "Klaar")
    return path
