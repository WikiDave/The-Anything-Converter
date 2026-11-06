"""Presets: named conversion settings, built in or saved by the user (in the settings file).

A preset has a name, the kinds of files it is for and the options for run_conversion (format, quality, codecs, ...).
Used by batches, watch folders, the terminal (--preset) and the app.
"""
from __future__ import annotations

import re

from . import settings

BUILTIN: dict[str, dict] = {
    "Web video (MP4 H.264, 1080p)": {"for": ["video"], "opts": {"format": "mp4", "vcodec": "h264", "acodec": "aac",
                                                                 "height": 1080, "quality": "medium"}},
    "Small video for WhatsApp (MP4, max 16 MB)": {"for": ["video"], "opts": {"format": "mp4",
                                                                            "target_bytes": 15 * 1024 * 1024}},
    "Apple / iPhone (MOV H.265)": {"for": ["video"], "opts": {"format": "mov", "vcodec": "h265", "acodec": "aac",
                                                              "quality": "high"}},
    "Archive video (MKV H.265, all tracks)": {"for": ["video"], "opts": {"format": "mkv", "vcodec": "h265",
                                                                         "streams": "all", "quality": "high"}},
    "GIF for chat (480 px)": {"for": ["video"], "opts": {"format": "gif", "gif_width": 480, "gif_fps": 12}},
    "Audio to MP3 (192 kbps)": {"for": ["audio", "video"], "opts": {"format": "mp3", "audio_bitrate": 192}},
    "Audio lossless (FLAC)": {"for": ["audio", "video"], "opts": {"format": "flac"}},
    "Photos to JPG": {"for": ["image"], "opts": {"format": "jpg", "quality": "high"}},
    "Photos for the web (WebP)": {"for": ["image"], "opts": {"format": "webp", "quality": "medium"}},
    "Photos smaller (JPG, 50%)": {"for": ["image"], "opts": {"format": "jpg", "scale_percent": 50,
                                                             "quality": "medium"}},
    "Documents to PDF": {"for": ["document", "spreadsheet", "presentation", "text", "image"],
                         "opts": {"format": "pdf"}},
    "Compress PDF": {"for": ["pdf"], "opts": {"format": "pdf", "quality": "low"}},
    "PDF to Word": {"for": ["pdf"], "opts": {"format": "docx"}},
    "Speech to text (TXT)": {"for": ["audio", "video"], "opts": {"format": "txt", "language": "auto",
                                                                 "speech_model": "base"}},
    "Subtitles from speech (SRT)": {"for": ["audio", "video"], "opts": {"format": "srt", "language": "auto",
                                                                        "speech_model": "base"}},
    "E-book to EPUB": {"for": ["ebook", "document"], "opts": {"format": "epub"}},
}
# options a preset may hold (nothing that points at files or runs commands)
ALLOWED = {"format", "quality", "target_bytes", "height", "width", "scale_percent", "device", "remove_audio",
           "vcodec", "acodec", "fps", "video_bitrate", "crf", "preset", "pix_fmt", "streams", "hw", "audio_bitrate",
           "sample_rate", "channels", "volume", "metadata", "gif_width", "gif_fps", "language", "speech_model",
           "translate", "meta_title", "meta_artist", "meta_album", "meta_date", "meta_comment"}


def _clean(opts: dict) -> dict:
    return {k: v for k, v in (opts or {}).items() if k in ALLOWED and v not in (None, "", False)}


def all_presets() -> dict[str, dict]:
    own = settings.load().get("presets", {})
    out = {k: dict(v, builtin=True) for k, v in BUILTIN.items()}
    out.update({k: dict(v, builtin=False) for k, v in own.items()})
    return out


def resolve(name: str) -> str:
    """The exact preset name for 'name' (also short forms such as 'photos to jpg')."""
    allp = all_presets()
    if name in allp:
        return name
    key = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    hit = next((k for k in allp if re.sub(r"[^a-z0-9]+", "", k.lower()).startswith(key)), None) if key else None
    if not hit:
        raise KeyError(name)
    return hit


def get(name: str) -> dict:
    p = all_presets().get(name)
    if not p:
        # also accept a simple form: 'web-video' for 'Web video (MP4 H.264, 1080p)'
        key = re.sub(r"[^a-z0-9]+", "", name.lower())
        p = next((v for k, v in all_presets().items() if re.sub(r"[^a-z0-9]+", "", k.lower()).startswith(key)), None)
    if not p:
        raise KeyError(name)
    return p


def save(name: str, kinds: list[str], opts: dict) -> dict:
    name = re.sub(r"\s+", " ", name or "").strip()[:80]
    if not name:
        raise ValueError("Give the preset a name.")
    if name in BUILTIN:
        raise ValueError("A built-in preset has this name; choose another name.")
    clean = _clean(opts)
    if not clean.get("format"):
        raise ValueError("A preset needs an output format.")
    s = settings.load()
    s.setdefault("presets", {})[name] = {"for": [k for k in kinds if isinstance(k, str)][:12], "opts": clean}
    settings.save(s)
    return s["presets"][name]


def delete(name: str) -> None:
    s = settings.load()
    if name in s.get("presets", {}):
        del s["presets"][name]
        settings.save(s)
