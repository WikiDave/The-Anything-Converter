"""Social media: foto's en video's op het exacte formaat van elk platform (zelfde lijst als de web-app).

- vullen: bijsnijden vanuit het midden tot precies het formaat (geen randen)
- passend: alles zichtbaar, aangevuld met een vervaagde achtergrond
- panorama: een brede foto in stukken voor een swipe-carrousel (Instagram, Facebook, Threads)
"""
from __future__ import annotations

import io
import math
import zipfile
from pathlib import Path
from typing import Callable, Optional

from .util import ConversionError

ProgressFn = Callable[[float, str], None]

# (platform, id, omschrijving, breedte, hoogte, extra)
PRESETS = [
    ("Instagram", "ig-portrait", "portrait post 4:5 · best in the feed", 1080, 1350, {}),
    ("Instagram", "ig-square", "post vierkant 1:1", 1080, 1080, {}),
    ("Instagram", "ig-land", "post liggend 1.91:1", 1080, 566, {}),
    ("Instagram", "ig-story", "story / reels 9:16", 1080, 1920, {"vbr": 6e6}),
    ("Instagram", "ig-pano", "panorama-carrousel 4:5 · swipen", 1080, 1350, {"pano": True}),
    ("Instagram", "ig-pano-sq", "panorama-carrousel 1:1 · swipen", 1080, 1080, {"pano": True}),
    ("Instagram", "ig-profile", "profielfoto", 320, 320, {}),
    ("Facebook", "fb-portrait", "post staand 4:5", 1080, 1350, {"max": 10e6}),
    ("Facebook", "fb-square", "post vierkant", 1080, 1080, {"max": 10e6}),
    ("Facebook", "fb-land", "post liggend / link", 1200, 630, {"max": 10e6}),
    ("Facebook", "fb-story", "story / reels 9:16", 1080, 1920, {"vbr": 6e6}),
    ("Facebook", "fb-cover", "omslagfoto", 1640, 624, {"max": 10e6}),
    ("Facebook", "fb-event", "evenementfoto", 1920, 1005, {}),
    ("Facebook", "fb-pano", "panorama-carrousel 4:5 · swipen", 1080, 1350, {"pano": True}),
    ("Facebook", "fb-profile", "profielfoto", 720, 720, {}),
    ("YouTube", "yt-1080", "video 1080p 16:9", 1920, 1080, {"vbr": 10e6}),
    ("YouTube", "yt-1440", "video 1440p 16:9 · scherper na upload", 2560, 1440, {"vbr": 18e6}),
    ("YouTube", "yt-4k", "video 4K 16:9", 3840, 2160, {"vbr": 40e6}),
    ("YouTube", "yt-shorts", "shorts 9:16", 1080, 1920, {"vbr": 10e6}),
    ("YouTube", "yt-thumb", "thumbnail", 1280, 720, {"max": 2e6}),
    ("YouTube", "yt-banner", "kanaalbanner", 2560, 1440, {"max": 6e6}),
    ("YouTube", "yt-profile", "profielfoto", 800, 800, {}),
    ("TikTok", "tt-video", "video 9:16", 1080, 1920, {"vbr": 6e6}),
    ("TikTok", "tt-photo", "foto 9:16", 1080, 1920, {}),
    ("TikTok", "tt-profile", "profielfoto", 400, 400, {}),
    ("X / Twitter", "x-land", "post liggend 16:9", 1600, 900, {"max": 5e6}),
    ("X / Twitter", "x-portrait", "post staand 4:5", 1080, 1350, {"max": 5e6}),
    ("X / Twitter", "x-video", "video 16:9", 1920, 1080, {"vbr": 6e6}),
    ("X / Twitter", "x-header", "header", 1500, 500, {"max": 5e6}),
    ("X / Twitter", "x-profile", "profielfoto", 400, 400, {"max": 2e6}),
    ("LinkedIn", "li-portrait", "post staand 4:5", 1080, 1350, {}),
    ("LinkedIn", "li-land", "post liggend", 1200, 627, {}),
    ("LinkedIn", "li-video", "video 16:9", 1920, 1080, {"vbr": 5e6}),
    ("LinkedIn", "li-banner", "profielbanner", 1584, 396, {}),
    ("LinkedIn", "li-profile", "profielfoto", 400, 400, {}),
    ("Pinterest", "pin", "pin 2:3", 1000, 1500, {"max": 20e6}),
    ("Pinterest", "pin-video", "video-pin 9:16", 1080, 1920, {"vbr": 6e6}),
    ("Snapchat", "snap", "story / spotlight 9:16", 1080, 1920, {"vbr": 6e6}),
    ("Threads", "threads", "post staand 4:5", 1080, 1350, {}),
    ("Threads", "threads-pano", "panorama-carrousel 4:5 · swipen", 1080, 1350, {"pano": True}),
    ("WhatsApp", "wa-status", "status 9:16", 1080, 1920, {"vbr": 4e6}),
    ("WhatsApp", "wa-profile", "profielfoto", 640, 640, {}),
    ("Bluesky", "bsky", "post 4:5 · max 1 MB", 1600, 2000, {"max": 0.95e6}),
    ("Twitch", "twitch-banner", "profielbanner", 1200, 480, {}),
    ("Twitch", "twitch-thumb", "stream-thumbnail", 1920, 1080, {}),
]
BY_ID = {p[1]: p for p in PRESETS}


def label(pid: str) -> str:
    g, _, name, w, h, _ = BY_ID[pid]
    return f"{g} · {name} · {w}×{h}"


def _cover(im, w: int, h: int):
    from PIL import Image
    scale = max(w / im.width, h / im.height)
    r = im.resize((max(w, round(im.width * scale)), max(h, round(im.height * scale))), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def _contain(im, w: int, h: int):
    from PIL import Image, ImageFilter
    bg = _cover(im, w, h).filter(ImageFilter.GaussianBlur(40)).point(lambda v: int(v * 0.55))
    scale = min(w / im.width, h / im.height)
    fg = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
    return bg


def _save_jpg(im, max_bytes: float) -> bytes:
    for q in (92, 88, 84, 80, 75, 70, 62, 55):
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        if buf.tell() <= max_bytes:
            break
    return buf.getvalue()


def image(src: Path, out_dir: Path, pid: str, fit: str = "cover", progress: Optional[ProgressFn] = None) -> Path:
    from PIL import Image, ImageOps
    if pid not in BY_ID:
        raise ConversionError("Unknown social media size.")
    g, _, name, w, h, extra = BY_ID[pid]
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    max_bytes = extra.get("max", 8e6)
    if extra.get("pano"):
        # aantal stukken: zo dat de volle hoogte in beeld blijft
        n = max(2, min(20, math.ceil(im.width / im.height * h / w - 0.05)))
        strip = _cover(im, w * n, h)
        out = out_dir / f"{src.stem}_{pid}_{n}-delen.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
            for i in range(n):
                z.writestr(f"{src.stem}_{i + 1:02d}-of-{n}.jpg", _save_jpg(strip.crop((i * w, 0, (i + 1) * w, h)),
                                                                            max_bytes))
                if progress:
                    progress(0.2 + 0.75 * (i + 1) / n, f"deel {i + 1}/{n}")
        return out
    res = _cover(im, w, h) if fit == "cover" else _contain(im, w, h)
    out = out_dir / f"{src.stem}_{pid}.jpg"
    out.write_bytes(_save_jpg(res, max_bytes))
    return out


def video(src: Path, out_dir: Path, pid: str, fit: str = "cover", progress: Optional[ProgressFn] = None) -> Path:
    from .media import _probe, _run_ffmpeg
    if pid not in BY_ID:
        raise ConversionError("Unknown social media size.")
    g, _, name, w, h, extra = BY_ID[pid]
    if extra.get("pano"):
        raise ConversionError("A panorama carousel can only be made from a photo.")
    info = _probe(src)
    kbps = int(extra.get("vbr", 6e6) / 1000)
    if fit == "cover":
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"
    else:
        vf = (f"split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=30:5,"
              f"eq=brightness=-0.15[bg];[b]scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos[fg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2")
    out = out_dir / f"{src.stem}_{pid}.mp4"
    flag = "-vf" if fit == "cover" else "-filter_complex"
    args = ["-i", str(src), flag, vf + ",format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-profile:v", "high",
            "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.5)}k", "-bufsize", f"{kbps * 2}k", "-r", "30"]
    args += ["-c:a", "aac", "-b:a", "160k", "-ar", "48000"] if info["has_audio"] else ["-an"]
    _run_ffmpeg([*args, "-movflags", "+faststart", str(out)], info["duration"], progress, label="Video maken")
    return out
