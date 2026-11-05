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


# --------------------------------------------------------------------------- advanced settings
# Everything "behind" a media file: codecs, frame rate, resolution, bitrates, audio channels and metadata.

V_ENCODERS = {"h264": "libx264", "h265": "libx265", "vp9": "libvpx-vp9", "vp8": "libvpx", "av1": "libsvtav1",
              "prores": "prores_ks", "dnxhd": "dnxhd", "mpeg4": "mpeg4", "mpeg2": "mpeg2video", "mjpeg": "mjpeg",
              "theora": "libtheora", "copy": "copy"}
A_ENCODERS = {"aac": "aac", "mp3": "libmp3lame", "opus": "libopus", "vorbis": "libvorbis", "flac": "flac",
              "ac3": "ac3", "eac3": "eac3", "alac": "alac", "pcm": "pcm_s16le", "pcm24": "pcm_s24le", "mp2": "mp2",
              "copy": "copy"}
# Which codecs each container can hold (a missing container = no limits checked).
CONTAINER_V = {"mp4": {"h264", "h265", "av1", "vp9", "mpeg4", "mpeg2", "mjpeg", "copy"},
               "m4v": {"h264", "h265", "av1", "mpeg4", "copy"},
               "mov": {"h264", "h265", "prores", "dnxhd", "mjpeg", "mpeg4", "av1", "copy"},
               "webm": {"vp9", "vp8", "av1", "copy"},
               "avi": {"h264", "mpeg4", "mjpeg", "mpeg2", "copy"},
               "ogv": {"theora", "vp8", "copy"},
               "mkv": set(V_ENCODERS)}
CONTAINER_A = {"mp4": {"aac", "mp3", "opus", "flac", "ac3", "eac3", "alac", "copy"},
               "m4v": {"aac", "ac3", "alac", "copy"},
               "mov": {"aac", "mp3", "alac", "pcm", "pcm24", "ac3", "copy"},
               "webm": {"opus", "vorbis", "copy"},
               "avi": {"mp3", "ac3", "pcm", "mp2", "aac", "copy"},
               "ogv": {"vorbis", "opus", "flac", "copy"},
               "mkv": set(A_ENCODERS)}
CRF_EXTRA = {"libx265": {"high": 22, "medium": 26, "low": 32}, "libsvtav1": {"high": 28, "medium": 35, "low": 45},
             "libaom-av1": {"high": 28, "medium": 35, "low": 45}, "libvpx": {"high": 8, "medium": 12, "low": 20}}
META_FIELDS = ("title", "artist", "album", "date", "genre", "comment", "description", "copyright", "language")
_encoders_cache: set[str] | None = None


def encoders() -> set[str]:
    global _encoders_cache
    if _encoders_cache is None:
        try:
            out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20,
                                 **NO_WINDOW).stdout
            _encoders_cache = {ln.split()[1] for ln in out.splitlines() if len(ln.split()) > 1 and ln.startswith(" ")
                               and len(ln.split()[0]) == 6}
        except (OSError, subprocess.SubprocessError):
            _encoders_cache = set()
    return _encoders_cache


def _pick_encoder(name: str) -> str:
    enc = V_ENCODERS.get(name) or A_ENCODERS.get(name) or name
    have = encoders()
    if enc == "libsvtav1" and have and enc not in have and "libaom-av1" in have:
        return "libaom-av1"
    if have and enc != "copy" and enc not in have:
        raise ConversionError(f"This ffmpeg has no {name.upper()} encoder ({enc}).")
    return enc


def _check_container(fmt: str, vname: str | None, aname: str | None) -> None:
    if vname and fmt in CONTAINER_V and vname not in CONTAINER_V[fmt]:
        raise ConversionError(f"A .{fmt} file cannot hold {vname.upper()} video. Possible: "
                              f"{', '.join(sorted(c for c in CONTAINER_V[fmt] if c != 'copy')).upper()}.")
    if aname and fmt in CONTAINER_A and aname not in CONTAINER_A[fmt]:
        raise ConversionError(f"A .{fmt} file cannot hold {aname.upper()} audio. Possible: "
                              f"{', '.join(sorted(c for c in CONTAINER_A[fmt] if c != 'copy')).upper()}.")


def _num(v, kind=float):
    try:
        return kind(str(v).strip().lower().rstrip("kps").rstrip("fps").strip()) if v not in (None, "") else None
    except ValueError:
        raise ConversionError(f"Not a number: {v}") from None


def metadata_args(opts: dict) -> list[str]:
    """keep (default) / strip / edit the tags and chapters of a file."""
    args = ["-map_metadata", "-1", "-map_chapters", "-1"] if opts.get("metadata") == "strip" else \
        ["-map_metadata", "0"]
    for k in META_FIELDS:
        v = opts.get(f"meta_{k}")
        if v is not None and str(v) != "":
            args += ["-metadata", f"{k}={str(v)[:1000]}"]
    return args


def audio_extra(opts: dict) -> list[str]:
    args = []
    if opts.get("sample_rate"):
        args += ["-ar", str(int(_num(opts["sample_rate"])))]
    if opts.get("channels"):
        ch = {"mono": 1, "stereo": 2, "5.1": 6}.get(str(opts["channels"]), None) or int(_num(opts["channels"]))
        args += ["-ac", str(ch)]
    if opts.get("volume"):
        args += ["-af", f"volume={_num(opts['volume'])}dB"]
    return args


def media_info(src: Path) -> dict:
    """Everything behind a media file, for the settings panel: container, streams, codecs and tags."""
    info = ffprobe(src)
    fmt = info.get("format", {})
    streams = []
    for st in info.get("streams", []):
        kind = st.get("codec_type")
        row = {"index": st.get("index"), "kind": kind, "codec": st.get("codec_name"),
               "codec_long": st.get("codec_long_name"), "profile": st.get("profile"),
               "bitrate": int(st.get("bit_rate") or 0), "language": (st.get("tags") or {}).get("language"),
               "title": (st.get("tags") or {}).get("title")}
        if kind == "video":
            num, _, den = (st.get("avg_frame_rate") or st.get("r_frame_rate") or "0/1").partition("/")
            fps = float(num) / float(den or 1) if float(den or 1) else 0
            row.update(width=st.get("width"), height=st.get("height"), fps=round(fps, 3),
                       pix_fmt=st.get("pix_fmt"), color=st.get("color_transfer"),
                       cover=bool(st.get("disposition", {}).get("attached_pic")))
        elif kind == "audio":
            row.update(sample_rate=int(st.get("sample_rate") or 0), channels=st.get("channels"),
                       layout=st.get("channel_layout"))
        streams.append(row)
    return {"container": fmt.get("format_long_name") or fmt.get("format_name"),
            "duration": float(fmt.get("duration") or 0), "bitrate": int(fmt.get("bit_rate") or 0),
            "size": int(fmt.get("size") or 0), "tags": fmt.get("tags") or {},
            "chapters": len(info.get("chapters", []) or []), "streams": streams}


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
        "vcodec": v.get("codec_name") if v else None,
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
                lo: float = 0.0, hi: float = 1.0, label: str = "Working") -> None:
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
        raise ConversionError("ffmpeg failed:\n" + tail)


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
        raise ConversionError("The start point is after the end of the file.")
    if end is not None:
        if full:
            end = min(end, full)
        if end <= start:
            raise ConversionError("The end point must be after the start point.")
    duration = (end if end is not None else full) - start
    trimming = start > 0 or end is not None

    trim_args: list[str] = []
    if start > 0:
        trim_args += ["-ss", f"{start:.3f}"]
    if end is not None:
        trim_args += ["-t", f"{end - start:.3f}"]

    stem = src.stem + ("_edited" if fmt == src.suffix.lstrip(".").lower() else "")
    dst = out_dir / f"{stem}.{ {'alac': 'm4a'}.get(fmt, fmt)}"

    target = opts.get("target_bytes")
    quality = opts.get("quality") or "medium"

    # Snel knippen zonder hercoderen (zelfde formaat, geen andere wijzigingen)
    if opts.get("fast_trim") and fmt == src.suffix.lstrip(".").lower() and not target and not opts.get("height"):
        _run_ffmpeg([*trim_args, "-i", str(src), "-map", "0", "-c", "copy",
                     "-avoid_negative_ts", "make_zero", str(dst)], duration, progress, label="Trimming")
        return dst

    if fmt in AUDIO_ONLY:
        if not info["has_audio"]:
            raise ConversionError("This file has no audio.")
        return _audio(src, dst, fmt, trim_args, duration, target, quality, progress, info, opts)
    if fmt == "gif":
        return _gif(src, dst, trim_args, duration, info, opts, target, progress)
    if fmt not in VIDEO_CODEC:
        raise ConversionError(f"Output format .{fmt} is not supported for video.")
    if not info["has_video"]:
        raise ConversionError("This file has no video picture.")
    return _video(src, dst, fmt, trim_args, duration, info, opts, target, quality, progress, trimming)


VORBIS_Q = {"high": 6, "medium": 4, "low": 2}


def _audio(src, dst, fmt, trim_args, duration, target, quality, progress, info=None, opts=None) -> Path:
    info, opts = info or {}, opts or {}
    args = [*trim_args, "-i", str(src), "-vn", "-map", "0:a:0", *AUDIO_CODEC[fmt], *info.get("fix_layout", [])]
    if target:
        if fmt in FIXED_AUDIO:
            raise ConversionError(f".{fmt} has a fixed quality; its size is fixed. Choose mp3, m4a, ogg or opus to reach a target size.")
        if duration <= 0:
            raise ConversionError("Cannot determine the duration, so no target size is possible.")
        kbps = target * 8 * CONTAINER_OVERHEAD / duration / 1000
        lo, hi = AUDIO_LIMITS[fmt]
        if kbps < lo:
            raise ConversionError(f"Target size too small: at least ~{human_size(int(lo * 1000 * duration / 8))} is needed for .{fmt} at this length.")
        kbps = min(int(kbps), hi)
        args += ["-b:a", f"{kbps}k"]
        if kbps < 64 and fmt in ("mp3", "m4a", "aac"):
            args += ["-ac", "1"]
    elif opts.get("audio_bitrate") and fmt not in FIXED_AUDIO:
        args += ["-b:a", f"{int(_num(opts['audio_bitrate']))}k"]
    elif fmt == "ogg":
        args += ["-q:a", str(VORBIS_Q[quality])]  # kwaliteitsstand: werkt ook bij lage samplerates (8 kHz)
    elif fmt not in FIXED_AUDIO:
        args += ["-b:a", f"{AUDIO_KBPS[quality]}k"]
    extra = audio_extra(opts)
    if extra:
        args = [a for a in args if a not in info.get("fix_layout", [])] + extra
    args += metadata_args(opts)
    if fmt == "m4r" and duration > 40 and "-t" not in trim_args:
        args += ["-t", "40"]  # iPhone-beltonen mogen maximaal 40 seconden zijn
    if fmt in ("m4a", "m4r", "m4b", "alac"):
        args += ["-movflags", "+faststart"]
    _run_ffmpeg([*args, str(dst)], duration, progress, label="Encoding audio")
    return dst


def _scale_filter(height: Optional[int]) -> list[str]:
    return [f"scale=-2:{int(height)}:flags=lanczos"] if height else []


SVT_PRESET = {"ultrafast": 12, "superfast": 11, "veryfast": 10, "faster": 9, "fast": 8, "medium": 6, "slow": 4,
              "slower": 3, "veryslow": 2}
SUB_CODEC = {"mp4": "mov_text", "m4v": "mov_text", "mov": "mov_text", "webm": "webvtt", "mkv": "copy"}


def _video(src, dst, fmt, trim_args, duration, info, opts, target, quality, progress, trimming) -> Path:
    vcodec, acodec = VIDEO_CODEC[fmt]
    vname = (opts.get("vcodec") or "").lower() or None
    aname = (opts.get("acodec") or "").lower() or None
    _check_container(fmt, vname, aname)
    if vname:
        vcodec = _pick_encoder(vname)
    if aname:
        acodec = _pick_encoder(aname)
    keep_audio = info["has_audio"] and not opts.get("remove_audio")
    height = int(opts["height"]) if opts.get("height") else None
    width = int(opts["width"]) if opts.get("width") else None
    fps = _num(opts.get("fps"))
    device = DEVICES.get(opts.get("device") or "")
    if device and (height or info["height"] or 0) > device[0]:
        height = device[0]
    all_streams = opts.get("streams") == "all"

    base_in = [*trim_args, "-i", str(src), "-map", "0:v:0"]
    if keep_audio:
        base_in += ["-map", "0:a?" if all_streams else "0:a:0?"]
    subs: list[str] = []
    if all_streams and fmt in SUB_CODEC:
        base_in += ["-map", "0:s?"]
        subs = ["-c:s", SUB_CODEC[fmt]]
    meta = metadata_args(opts)

    filters = []
    if width and height:
        filters.append(f"scale={width}:{height}:flags=lanczos")
    elif width:
        filters.append(f"scale={width}:-2:flags=lanczos")
    else:
        filters += _scale_filter(height)
    if fps:
        filters.append(f"fps={fps:g}")
    if not filters and ((info.get("width") or 0) % 2 or (info.get("height") or 0) % 2):
        filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")  # 4:2:0 video needs even sizes (e.g. a 161x91 GIF)
    if vcodec == "copy":
        if filters or target:
            raise ConversionError("Copying the video stream (no re-encoding) cannot change the size, resolution or "
                                  "frame rate. Choose a codec instead of 'copy'.")
        args = [*base_in, "-c:v", "copy"]
        if keep_audio:
            args += ["-c:a", acodec] + ([] if acodec == "copy" else
                                        ["-b:a", str(opts.get("audio_bitrate") or f"{AUDIO_KBPS[quality]}k")]
                                        + audio_extra(opts))
        else:
            args += ["-an"]
        if vname == "copy" and fmt in ("mp4", "mov", "m4v") and info.get("vcodec") == "hevc":
            args += ["-tag:v", "hvc1"]
        tail = (["-movflags", "+faststart"] if fmt in ("mp4", "mov", "m4v") else []) + VIDEO_EXTRA.get(fmt, [])
        _run_ffmpeg([*args, *subs, *meta, *tail, str(dst)], duration, progress, label="Copying streams")
        return dst

    pix = opts.get("pix_fmt") or ("yuv422p10le" if vcodec in ("prores_ks", "dnxhd") else "yuv420p")
    if pix == "10bit":
        pix = "yuv420p10le"
    common_v = ["-c:v", vcodec, "-pix_fmt", pix]
    preset = opts.get("preset")
    if vcodec in ("libx264", "libx265"):
        common_v += ["-preset", preset or "medium"]
        if device and vcodec == "libx264":
            common_v += ["-profile:v", device[1], "-level", device[2]]
        if vcodec == "libx265" and fmt in ("mp4", "mov", "m4v"):
            common_v += ["-tag:v", "hvc1"]  # so Apple devices play it
    elif vcodec == "libvpx-vp9":
        common_v += ["-row-mt", "1", "-deadline", "good", "-cpu-used", "2"]
    elif vcodec == "libsvtav1":
        common_v += ["-preset", str(SVT_PRESET.get(preset or "medium", 6))]
    elif vcodec == "libaom-av1":
        common_v += ["-cpu-used", "6", "-row-mt", "1"]
    elif vcodec == "prores_ks":
        common_v += ["-profile:v", str(opts.get("prores_profile") or 3), "-vendor", "apl0"]
    elif vcodec == "dnxhd":
        common_v = ["-c:v", "dnxhd", "-profile:v", "dnxhr_hq", "-pix_fmt", "yuv422p"]
    tail = (["-movflags", "+faststart"] if fmt in ("mp4", "mov", "m4v") else []) + VIDEO_EXTRA.get(fmt, [])
    if fps and "-r" in tail:
        i = tail.index("-r")
        tail = tail[:i] + tail[i + 2:]

    def audio_args(kbps: int | None) -> list[str]:
        if not keep_audio:
            return ["-an"]
        if acodec == "copy":
            return ["-c:a", "copy"]
        out = ["-c:a", acodec]
        if acodec not in ("flac", "alac", "pcm_s16le", "pcm_s24le"):
            if opts.get("audio_bitrate"):
                out += ["-b:a", f"{int(_num(opts['audio_bitrate']))}k"]
            elif kbps:
                out += ["-b:a", f"{kbps}k"]
            elif acodec == "libvorbis":
                out += ["-q:a", str(VORBIS_Q[quality])]
            else:
                out += ["-b:a", f"{AUDIO_KBPS[quality]}k"]
        extra = audio_extra(opts)
        return out + (extra if extra else info.get("fix_layout", []))

    vf = ["-vf", ",".join(filters)] if filters else []
    if not target:
        crf = CRF.get(vcodec) or CRF_EXTRA.get(vcodec)
        if opts.get("video_bitrate"):
            vb = int(_num(opts["video_bitrate"]))
            rate = ["-b:v", f"{vb}k", "-maxrate", f"{int(vb * 1.5)}k", "-bufsize", f"{vb * 2}k"]
        elif vcodec in ("prores_ks", "dnxhd"):
            rate = []
        elif opts.get("crf") not in (None, "") and crf:
            rate = ["-crf", str(int(_num(opts["crf"])))]
        elif crf:
            rate = ["-crf", str(crf[quality])]
        else:
            rate = ["-q:v", str(QSCALE.get(vcodec, QSCALE["mpeg4"])[quality])]
        if vcodec == "libvpx-vp9" and "-crf" in rate:
            rate += ["-b:v", "0"]
        _run_ffmpeg([*base_in, *common_v, *rate, *vf, *audio_args(None), *subs, *meta, *tail, str(dst)],
                    duration, progress, label="Encoding video")
        return dst

    # ---- target size: 2-pass encode with a calculated bitrate
    if duration <= 0:
        raise ConversionError("Cannot determine the duration, so no target size is possible.")
    total_kbps = target * 8 * CONTAINER_OVERHEAD / duration / 1000
    a_kbps = (int(_num(opts["audio_bitrate"])) if opts.get("audio_bitrate") else _audio_bitrate_for(total_kbps)) \
        if keep_audio else 0
    v_kbps = total_kbps - a_kbps
    if v_kbps < 30:
        need = int((30 + a_kbps) * 1000 * duration / 8 / CONTAINER_OVERHEAD)
        raise ConversionError(f"Target size too small for this video length. At least about {human_size(need)}; trim the video or remove the audio.")
    if not height and not width and info["height"]:
        height = _auto_height(v_kbps, info["height"])
        if height:
            filters.insert(0, _scale_filter(height)[0])
    vf = ["-vf", ",".join(filters)] if filters else []

    src_kbps = info["bitrate"] / 1000 if info["bitrate"] else 0
    growing = src_kbps and total_kbps > src_kbps * 1.05
    v_kbps = int(v_kbps)
    rate = ["-b:v", f"{v_kbps}k"]
    if growing:
        # Making it larger: force a constant bitrate so the file really grows.
        rate += ["-minrate", f"{v_kbps}k", "-maxrate", f"{v_kbps}k", "-bufsize", f"{v_kbps * 2}k"]
        if vcodec == "libx264":
            rate += ["-x264-params", "nal-hrd=cbr:force-cfr=1"]
    else:
        rate += ["-maxrate", f"{int(v_kbps * 1.5)}k", "-bufsize", f"{v_kbps * 2}k"]
    if vcodec in ("prores_ks", "dnxhd"):
        raise ConversionError("ProRes and DNxHD have a fixed quality; a target size is not possible. Choose H.264 or H.265.")

    passlog = str(dst.parent / f"{dst.stem}_2pass")
    two_pass = vcodec in ("libx264", "libx265", "libvpx-vp9", "libvpx", "mpeg4", "mpeg2video")
    if two_pass:
        pass1 = ["-pass", "1", "-passlogfile", passlog] if vcodec != "libx265" else \
            ["-x265-params", f"pass=1:stats={passlog}.log"]
        pass2 = ["-pass", "2", "-passlogfile", passlog] if vcodec != "libx265" else \
            ["-x265-params", f"pass=2:stats={passlog}.log"]
        _run_ffmpeg([*base_in, *common_v, *rate, *vf, *pass1, "-an", "-f", "null", "/dev/null"],
                    duration, progress, 0.0, 0.5, "Analysis (pass 1/2)")
        _run_ffmpeg([*base_in, *common_v, *rate, *vf, *pass2, *audio_args(a_kbps), *subs, *meta, *tail, str(dst)],
                    duration, progress, 0.5, 1.0, "Encoding (pass 2/2)")
    else:
        _run_ffmpeg([*base_in, *common_v, *rate, *vf, *audio_args(a_kbps), *subs, *meta, *tail, str(dst)],
                    duration, progress, label="Encoding video")
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
            raise ConversionError("The GIF could not be made small enough. Trim the video.")
    return dst
