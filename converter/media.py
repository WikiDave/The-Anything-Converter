"""Video en audio: converteren, knippen en naar een doelgrootte comprimeren (ffmpeg)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from .util import NO_WINDOW, ConversionError, ProgressFn, ffprobe, parse_time, human_size

AUDIO_ONLY = {"mp3", "m4a", "aac", "wav", "flac", "ogg", "opus", "aiff", "wma", "m4r", "mmf", "ac3", "eac3", "wv",
              "tta", "au", "caf", "mka", "m4b", "spx", "alac"}
LOSSLESS_AUDIO = {"wav", "flac", "aiff", "wv", "tta", "au", "alac"}
FIXED_AUDIO = LOSSLESS_AUDIO | {"mmf"}  # geen bitrate te kiezen

AUDIO_CODEC = {
    "mp3": ["-c:a", "libmp3lame"],
    "m4a": ["-c:a", "aac"],
    "aac": ["-c:a", "aac"],
    "ogg": ["-c:a", "libvorbis"],
    "opus": ["-c:a", "libopus"],
    "wav": ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac"],
    "aiff": ["-c:a", "pcm_s16be"],
    "wma": ["-c:a", "wmav2"],
    "m4r": ["-c:a", "aac", "-f", "ipod"],  # iPhone-beltoon
    "mmf": ["-c:a", "adpcm_yamaha", "-ar", "8000", "-ac", "1"],  # beltoon (Yamaha SMAF)
    "ac3": ["-c:a", "ac3"],
    "eac3": ["-c:a", "eac3"],
    "wv": ["-c:a", "wavpack"],
    "tta": ["-c:a", "tta"],
    "au": ["-c:a", "pcm_s16be"],
    "caf": ["-c:a", "alac"],
    "mka": ["-c:a", "libopus"],
    "m4b": ["-c:a", "aac", "-f", "ipod"],  # audioboek
    "spx": ["-c:a", "libspeex", "-ar", "16000", "-ac", "1"],
    "alac": ["-c:a", "alac", "-f", "ipod"],
}
AUDIO_LIMITS = {"mp3": (8, 320), "m4a": (16, 512), "aac": (16, 512), "ogg": (45, 500), "opus": (6, 510),
                "wma": (32, 320), "m4r": (16, 512), "ac3": (64, 640), "eac3": (32, 1536), "mka": (6, 510),
                "m4b": (16, 512), "spx": (4, 44)}

VIDEO_CODEC = {
    "mp4": ("libx264", "aac"),
    "mov": ("libx264", "aac"),
    "mkv": ("libx264", "aac"),
    "avi": ("libx264", "libmp3lame"),
    "webm": ("libvpx-vp9", "libopus"),
    "3gp": ("libx264", "aac"),
    "3g2": ("libx264", "aac"),
    "flv": ("libx264", "aac"),
    "mpg": ("mpeg2video", "mp2"),
    "ogv": ("libtheora", "libvorbis"),
    "wmv": ("wmv2", "wmav2"),
    "asf": ("wmv2", "wmav2"),
    "m4v": ("libx264", "aac"),
    "ts": ("libx264", "aac"),
    "m2ts": ("libx264", "ac3"),
    "divx": ("mpeg4", "libmp3lame"),
    "mxf": ("mpeg2video", "pcm_s16le"),
}
# Apparaat-presets: maximale hoogte en H.264-profiel/-niveau dat het apparaat zeker afspeelt
DEVICES = {
    "iphone": (1080, "high", "4.1"), "ipad": (1080, "high", "4.1"), "android": (1080, "high", "4.1"),
    "ipod": (480, "baseline", "3.0"), "playstation": (1080, "high", "4.1"), "psp": (272, "main", "3.0"),
    "xbox": (1080, "high", "4.1"), "nintendo-switch": (720, "high", "4.0"), "nintendo-3ds": (240, "baseline", "3.0"),
    "wii": (480, "baseline", "3.0"), "blackberry": (480, "baseline", "3.0"), "kindle-fire": (720, "main", "3.1"),
}

# Extra muxer-opties per uitvoerformaat
VIDEO_EXTRA = {"divx": ["-f", "avi"], "mxf": ["-r", "25", "-ar", "48000"], "m2ts": ["-f", "mpegts"],
               "ts": ["-f", "mpegts"], "asf": ["-f", "asf"]}

# Codecs zonder CRF: vaste kwaliteit via -q:v (theora: hoger = beter, de rest: lager = beter)
QSCALE = {"mpeg2video": {"high": 3, "medium": 5, "low": 9}, "wmv2": {"high": 3, "medium": 5, "low": 9},
          "mpeg4": {"high": 3, "medium": 5, "low": 9},
          "libtheora": {"high": 8, "medium": 6, "low": 4}}
CRF = {"libx264": {"high": 20, "medium": 24, "low": 30}, "libvpx-vp9": {"high": 31, "medium": 36, "low": 42}}
AUDIO_KBPS = {"high": 192, "medium": 128, "low": 96}
CONTAINER_OVERHEAD = 0.96  # marge voor container-/muxoverhead


# --------------------------------------------------------------------------- helpers

def _probe(src: Path) -> dict:
    info = ffprobe(src)
    fmt = info.get("format", {})
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    return {
        "duration": float(fmt.get("duration", 0) or 0),
        "bitrate": int(fmt.get("bit_rate", 0) or 0),
        "width": int(v["width"]) if v else 0,
        "height": int(v["height"]) if v else 0,
        "has_video": v is not None,
        "has_audio": a is not None,
        # sommige bronnen (TTA, Speex, ...) hebben geen kanaalindeling; encoders als AAC weigeren dan
        "fix_layout": _layout_fix(a),
        "sample_rate": int(a.get("sample_rate") or 0) if a else 0,
    }


def _layout_fix(a) -> list[str]:
    """Kanaalindeling vastleggen als de bron er geen heeft (TTA, Speex, ...): anders weigeren encoders als AAC."""
    if not a or a.get("channel_layout"):
        return []
    n = int(a.get("channels") or 2)
    return ["-af", "pan=mono|c0=c0" if n == 1 else "pan=stereo|c0=c0|c1=c1"]


def _run_ffmpeg(args: list[str], duration: float, progress: Optional[ProgressFn],
                lo: float = 0.0, hi: float = 1.0, label: str = "Bezig") -> None:
    cmd = ["ffmpeg", "-hide_banner", "-y", "-nostdin", "-progress", "pipe:1", "-nostats", *args]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", **NO_WINDOW)
    # stderr in een aparte thread lezen zodat de pipe niet volloopt
    import threading
    err_lines: list[str] = []
    t = threading.Thread(target=lambda: err_lines.extend(proc.stderr), daemon=True)
    t.start()
    for line in proc.stdout:
        if line.startswith("out_time_us=") and duration > 0 and progress:
            try:
                secs = int(line.split("=", 1)[1]) / 1e6
            except ValueError:
                continue
            frac = min(max(secs / duration, 0), 1)
            progress(lo + (hi - lo) * frac, label)
    proc.wait()
    t.join(timeout=5)
    if proc.returncode != 0:
        tail = "".join(err_lines[-8:]).strip()
        raise ConversionError("ffmpeg faalde:\n" + tail)


def _audio_bitrate_for(total_kbps: float) -> int:
    if total_kbps > 1500:
        return 160
    if total_kbps > 600:
        return 128
    if total_kbps > 250:
        return 96
    if total_kbps > 100:
        return 64
    return 32


def _auto_height(video_kbps: float, src_h: int) -> Optional[int]:
    """Kies automatisch een lagere resolutie als de bitrate erg krap is."""
    for limit, h in ((250, 360), (500, 480), (1200, 720), (3000, 1080)):
        if video_kbps < limit and src_h > h:
            return h
    return None


# --------------------------------------------------------------------------- main

def process(src: Path, out_dir: Path, opts: dict, progress: Optional[ProgressFn] = None) -> Path:
    info = _probe(src)
    fmt = (opts.get("format") or src.suffix.lstrip(".")).lower()
    if fmt == "jpeg":
        fmt = "jpg"

    start = parse_time(opts.get("trim_start")) or 0.0
    end = parse_time(opts.get("trim_end"))
    full = info["duration"]
    if full and start >= full:
        raise ConversionError("Het startpunt ligt na het einde van het bestand.")
    if end is not None:
        if full:
            end = min(end, full)
        if end <= start:
            raise ConversionError("Het eindpunt moet na het startpunt liggen.")
    duration = (end if end is not None else full) - start
    trimming = start > 0 or end is not None

    trim_args: list[str] = []
    if start > 0:
        trim_args += ["-ss", f"{start:.3f}"]
    if end is not None:
        trim_args += ["-t", f"{end - start:.3f}"]

    stem = src.stem + ("_bewerkt" if fmt == src.suffix.lstrip(".").lower() else "")
    dst = out_dir / f"{stem}.{ {'alac': 'm4a'}.get(fmt, fmt)}"

    target = opts.get("target_bytes")
    quality = opts.get("quality") or "medium"

    # Snel knippen zonder hercoderen (zelfde formaat, geen andere wijzigingen)
    if opts.get("fast_trim") and fmt == src.suffix.lstrip(".").lower() and not target and not opts.get("height"):
        _run_ffmpeg([*trim_args, "-i", str(src), "-map", "0", "-c", "copy",
                     "-avoid_negative_ts", "make_zero", str(dst)], duration, progress, label="Knippen")
        return dst

    if fmt in AUDIO_ONLY:
        if not info["has_audio"]:
            raise ConversionError("Dit bestand bevat geen audio.")
        return _audio(src, dst, fmt, trim_args, duration, target, quality, progress, info)
    if fmt == "gif":
        return _gif(src, dst, trim_args, duration, info, opts, target, progress)
    if fmt not in VIDEO_CODEC:
        raise ConversionError(f"Uitvoerformaat .{fmt} wordt niet ondersteund voor video.")
    if not info["has_video"]:
        raise ConversionError("Dit bestand bevat geen videobeeld.")
    return _video(src, dst, fmt, trim_args, duration, info, opts, target, quality, progress, trimming)


VORBIS_Q = {"high": 6, "medium": 4, "low": 2}


def _audio(src, dst, fmt, trim_args, duration, target, quality, progress, info=None) -> Path:
    info = info or {}
    args = [*trim_args, "-i", str(src), "-vn", "-map", "0:a:0", *AUDIO_CODEC[fmt], *info.get("fix_layout", [])]
    if target:
        if fmt in FIXED_AUDIO:
            raise ConversionError(f".{fmt} heeft een vaste kwaliteit; de grootte ligt vast. Kies mp3, m4a, ogg of opus "
                                  "om een doelgrootte te halen.")
        if duration <= 0:
            raise ConversionError("Kan de duur niet bepalen, dus geen doelgrootte mogelijk.")
        kbps = target * 8 * CONTAINER_OVERHEAD / duration / 1000
        lo, hi = AUDIO_LIMITS[fmt]
        if kbps < lo:
            raise ConversionError(f"Doelgrootte te klein: minimaal ~{human_size(int(lo * 1000 * duration / 8))} "
                                  f"nodig voor .{fmt} bij deze lengte.")
        kbps = min(int(kbps), hi)
        args += ["-b:a", f"{kbps}k"]
        if kbps < 64 and fmt in ("mp3", "m4a", "aac"):
            args += ["-ac", "1"]
    elif fmt == "ogg":
        args += ["-q:a", str(VORBIS_Q[quality])]  # kwaliteitsstand: werkt ook bij lage samplerates (8 kHz)
    elif fmt not in FIXED_AUDIO:
        args += ["-b:a", f"{AUDIO_KBPS[quality]}k"]
    if fmt == "m4r" and duration > 40 and "-t" not in trim_args:
        args += ["-t", "40"]  # iPhone-beltonen mogen maximaal 40 seconden zijn
    if fmt in ("m4a", "m4r", "m4b", "alac"):
        args += ["-movflags", "+faststart"]
    _run_ffmpeg([*args, str(dst)], duration, progress, label="Audio coderen")
    return dst


def _scale_filter(height: Optional[int]) -> list[str]:
    return [f"scale=-2:{int(height)}:flags=lanczos"] if height else []


def _video(src, dst, fmt, trim_args, duration, info, opts, target, quality, progress, trimming) -> Path:
    vcodec, acodec = VIDEO_CODEC[fmt]
    keep_audio = info["has_audio"] and not opts.get("remove_audio")
    height = int(opts["height"]) if opts.get("height") else None
    device = DEVICES.get(opts.get("device") or "")
    if device and (height or info["height"] or 0) > device[0]:
        height = device[0]

    base_in = [*trim_args, "-i", str(src), "-map", "0:v:0"]
    if keep_audio:
        base_in += ["-map", "0:a:0?"]

    common_v = ["-c:v", vcodec, "-pix_fmt", "yuv420p"]
    if vcodec == "libx264":
        common_v += ["-preset", "medium"]
        if device:
            common_v += ["-profile:v", device[1], "-level", device[2]]
    elif vcodec == "libvpx-vp9":
        common_v += ["-row-mt", "1", "-deadline", "good", "-cpu-used", "2"]
    tail = (["-movflags", "+faststart"] if fmt in ("mp4", "mov", "m4v") else []) + VIDEO_EXTRA.get(fmt, [])

    if not target:
        filters = _scale_filter(height)
        args = [*base_in, *common_v, *(["-crf", str(CRF[vcodec][quality])] if vcodec in CRF
                                        else ["-q:v", str(QSCALE[vcodec][quality])])]
        if vcodec == "libvpx-vp9":
            args += ["-b:v", "0"]
        if filters:
            args += ["-vf", ",".join(filters)]
        if keep_audio:
            rate = ["-q:a", str(VORBIS_Q[quality])] if acodec == "libvorbis" else ["-b:a", f"{AUDIO_KBPS[quality]}k"]
            args += ["-c:a", acodec, *rate, *info.get("fix_layout", [])]
        else:
            args += ["-an"]
        _run_ffmpeg([*args, *tail, str(dst)], duration, progress, label="Video coderen")
        return dst

    # ---- doelgrootte: 2-pass codering met berekende bitrate
    if duration <= 0:
        raise ConversionError("Kan de duur niet bepalen, dus geen doelgrootte mogelijk.")
    total_kbps = target * 8 * CONTAINER_OVERHEAD / duration / 1000
    a_kbps = _audio_bitrate_for(total_kbps) if keep_audio else 0
    v_kbps = total_kbps - a_kbps
    if v_kbps < 30:
        need = int((30 + a_kbps) * 1000 * duration / 8 / CONTAINER_OVERHEAD)
        raise ConversionError(f"Doelgrootte te klein voor deze videolengte. Minimaal ongeveer {human_size(need)}; "
                              "knip de video korter of verwijder de audio.")
    if not height and info["height"]:
        height = _auto_height(v_kbps, info["height"])
    filters = _scale_filter(height)

    src_kbps = info["bitrate"] / 1000 if info["bitrate"] else 0
    growing = src_kbps and total_kbps > src_kbps * 1.05
    v_kbps = int(v_kbps)
    rate = ["-b:v", f"{v_kbps}k"]
    if growing:
        # Groter maken: constante bitrate afdwingen zodat het bestand echt groeit.
        rate += ["-minrate", f"{v_kbps}k", "-maxrate", f"{v_kbps}k", "-bufsize", f"{v_kbps * 2}k"]
        if vcodec == "libx264":
            rate += ["-x264-params", "nal-hrd=cbr:force-cfr=1"]
    else:
        rate += ["-maxrate", f"{int(v_kbps * 1.5)}k", "-bufsize", f"{v_kbps * 2}k"]

    vf = ["-vf", ",".join(filters)] if filters else []
    passlog = str(dst.parent / f"{dst.stem}_2pass")
    _run_ffmpeg([*base_in, *common_v, *rate, *vf, "-pass", "1", "-passlogfile", passlog, "-an", "-f", "null",
                 "/dev/null"], duration, progress, 0.0, 0.5, "Analyse (pass 1/2)")
    audio = ["-c:a", acodec, "-b:a", f"{a_kbps}k"] if keep_audio else ["-an"]
    _run_ffmpeg([*base_in, *common_v, *rate, *vf, "-pass", "2", "-passlogfile", passlog, *audio, *tail, str(dst)],
                duration, progress, 0.5, 1.0, "Coderen (pass 2/2)")
    for f in dst.parent.glob(f"{dst.stem}_2pass*"):
        f.unlink(missing_ok=True)
    return dst


def _gif(src, dst, trim_args, duration, info, opts, target, progress) -> Path:
    fps = int(opts.get("gif_fps") or 12)
    width = int(opts.get("gif_width") or min(info["width"] or 480, 480))

    def encode(w: int, f: int, colors: int = 256) -> None:
        vf = (f"fps={f},scale={w}:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors={colors}"
              f":stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
        _run_ffmpeg([*trim_args, "-i", str(src), "-filter_complex", vf, "-loop", "0", str(dst)],
                    duration, progress, label="GIF maken")

    encode(width, fps)
    if target:
        colors = 256
        for _ in range(8):
            size = dst.stat().st_size
            if size <= target:
                break
            ratio = (target / size) ** 0.5
            width = max(80, int(width * max(min(ratio, 0.9), 0.5)))
            if width <= 160 and fps > 8:
                fps = 8
            colors = max(32, colors // 2) if width <= 200 else colors
            encode(width, fps, colors)
        if dst.stat().st_size > target:
            raise ConversionError("GIF kon niet klein genoeg gemaakt worden. Knip de video korter.")
    return dst
