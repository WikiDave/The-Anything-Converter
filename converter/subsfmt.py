"""Ondertitels, songteksten, afspeellijsten en MIDI.

Ondertitels: SRT, VTT, ASS/SSA, SBV, TTML/DFXP, SAMI, SCC, EBU-STL, MicroDVD (.sub), LRC
  -> SRT, VTT, ASS, SBV, TTML, LRC en platte tekst. Exotische soorten leest ffmpeg.
  Beeld-ondertitels (VobSub .sub/.idx, Blu-ray .sup) zijn plaatjes: daar is OCR voor nodig.
Afspeellijsten: M3U/M3U8, PLS, XSPF, WPL, ASX -> elk van deze, CSV of tekst.
MIDI: naar WAV/MP3/OGG met FluidSynth + een SoundFont (als die op de computer staan).
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

from .util import NO_WINDOW, ConversionError, have

SUBS = {"srt", "vtt", "ass", "ssa", "sbv", "ttml", "dfxp", "smi", "sami", "scc", "stl", "sub", "lrc"}
SUB_OUT = ["srt", "vtt", "ass", "sbv", "ttml", "lrc", "txt"]
PLAYLISTS = {"m3u", "m3u8", "pls", "xspf", "wpl", "asx", "ram"}
PL_OUT = ["m3u", "m3u8", "pls", "xspf", "wpl", "csv", "txt"]
MIDI = {"mid", "midi", "kar"}


def targets(ext: str) -> list[str]:
    if ext in PLAYLISTS:
        return [t for t in PL_OUT if t != ext]
    if ext in MIDI:
        return ["wav", "mp3", "ogg", "flac", "txt"]
    return [t for t in SUB_OUT if t != ext]


# --------------------------------------------------------------------------- ondertitels: lezen

def _ts(s: str) -> float:
    s = s.strip().replace(",", ".")
    parts = s.split(":")
    sec = 0.0
    for p in parts:
        sec = sec * 60 + float(p or 0)
    return sec


def _ttml_time(s: str, fps: float = 25.0) -> float:
    s = (s or "0").strip()
    m = re.fullmatch(r"([\d.]+)(h|m|s|ms|f|t)", s)
    if m:
        v, u = float(m.group(1)), m.group(2)
        return {"h": v * 3600, "m": v * 60, "s": v, "ms": v / 1000, "f": v / fps, "t": v / 10_000_000}[u]
    parts = s.split(":")
    if len(parts) == 4:  # hh:mm:ss:ff
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) + int(parts[3]) / fps
    return _ts(s)


def read_cues(path: Path) -> list[tuple[float, float, str]]:
    from .textfmt import read_text
    ext = path.suffix.lower().lstrip(".")
    if ext in ("ass", "ssa", "smi", "sami", "scc", "stl"):
        return _via_ffmpeg(path)
    text = read_text(path).replace("\r\n", "\n").replace("\r", "\n")
    cues = []
    if ext in ("srt", "vtt"):
        for block in re.split(r"\n\s*\n", text):
            m = re.search(r"((?:\d+:)?\d+:\d+[.,]\d+)\s*-->\s*((?:\d+:)?\d+:\d+[.,]\d+)[^\n]*\n(.*)", block, re.S)
            if m:
                body = re.sub(r"<[^>]+>", "", m.group(3)).strip()
                cues.append((_ts(m.group(1)), _ts(m.group(2)), body))
    elif ext == "sbv":
        for block in re.split(r"\n\s*\n", text):
            m = re.match(r"\s*([\d:.]+),([\d:.]+)\n(.*)", block, re.S)
            if m:
                cues.append((_ts(m.group(1)), _ts(m.group(2)), m.group(3).strip()))
    elif ext in ("ttml", "dfxp"):
        root = ET.fromstring(text.encode("utf-8"))
        for p in root.iter():
            if p.tag.split("}")[-1] != "p":
                continue
            parts = [p.text or ""]
            for c in p:
                parts.append("\n" if c.tag.split("}")[-1] == "br" else "".join(c.itertext()))
                parts.append(c.tail or "")
            b = _ttml_time(p.get("begin"))
            e = _ttml_time(p.get("end")) if p.get("end") else b + _ttml_time(p.get("dur", "2s"))
            cues.append((b, e, "".join(parts).strip()))
    elif ext == "sub":
        if path.with_suffix(".idx").exists() or not re.match(r"\{\d+\}", text):
            raise ConversionError("These are image subtitles (VobSub): pictures, not text. That needs OCR (e.g. Subtitle Edit).")
        fps = 25.0
        for line in text.splitlines():
            m = re.match(r"\{(\d+)\}\{(\d+)\}(.*)", line)
            if m:
                a, b, t = int(m.group(1)), int(m.group(2)), m.group(3)
                if a == b == 1 and re.fullmatch(r"[\d.]+", t):
                    fps = float(t)
                    continue
                cues.append((a / fps, b / fps, re.sub(r"\{[^}]*\}", "", t).replace("|", "\n")))
    elif ext == "lrc":
        times = []
        for line in text.splitlines():
            stamps = re.findall(r"\[(\d+):(\d+(?:\.\d+)?)\]", line)
            words = re.sub(r"\[[^\]]*\]", "", line).strip()
            for mm, ss in stamps:
                times.append((int(mm) * 60 + float(ss), words))
        times.sort()
        for i, (t, words) in enumerate(times):
            end = times[i + 1][0] if i + 1 < len(times) else t + 4
            if words:
                cues.append((t, end, words))
    if not cues:
        raise ConversionError("No subtitles found in this file.")
    return cues


def _via_ffmpeg(path: Path) -> list[tuple[float, float, str]]:
    import tempfile
    tmp = Path(tempfile.mkdtemp()) / "uit.srt"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-nostdin", "-i", str(path), str(tmp)], capture_output=True,
                       **NO_WINDOW)
    if r.returncode != 0 or not tmp.exists():
        raise ConversionError("These subtitles cannot be read: " +
                              r.stderr.decode("utf-8", "replace")[-200:])
    cues = read_cues(tmp)
    shutil.rmtree(tmp.parent, ignore_errors=True)
    return cues


# --------------------------------------------------------------------------- ondertitels: schrijven

def _stamp(t: float, sep: str = ",", hours: bool = True) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}" if hours else f"{m:02d}:{s:02d}{sep}{ms:03d}"


def write_cues(cues, dst: Path, fmt: str) -> Path:
    if fmt == "srt":
        dst.write_text("\n".join(f"{i}\n{_stamp(a)} --> {_stamp(b)}\n{t}\n" for i, (a, b, t) in enumerate(cues, 1)),
                       encoding="utf-8")
    elif fmt == "vtt":
        dst.write_text("WEBVTT\n\n" + "\n".join(f"{_stamp(a, '.')} --> {_stamp(b, '.')}\n{t}\n" for a, b, t in cues),
                       encoding="utf-8")
    elif fmt == "sbv":
        def sb(t):
            h, rest = divmod(t, 3600)
            m, s = divmod(rest, 60)
            return f"{int(h)}:{int(m):02d}:{s:06.3f}"
        dst.write_text("\n".join(f"{sb(a)},{sb(b)}\n{t}\n" for a, b, t in cues), encoding="utf-8")
    elif fmt == "lrc":
        dst.write_text("\n".join(f"[{int(a // 60):02d}:{a % 60:05.2f}]{t.replace(chr(10), ' ')}" for a, b, t in cues)
                       + "\n", encoding="utf-8")
    elif fmt == "txt":
        dst.write_text("\n".join(t for _, _, t in cues) + "\n", encoding="utf-8")
    elif fmt == "ttml":
        body = "\n".join(f'      <p begin="{_stamp(a, ".")}" end="{_stamp(b, ".")}">'
                         f'{html.escape(t).replace(chr(10), "<br/>")}</p>' for a, b, t in cues)
        dst.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<tt xmlns="http://www.w3.org/ns/ttml" xml:lang="nl">\n'
                       f"  <body>\n    <div>\n{body}\n    </div>\n  </body>\n</tt>\n", encoding="utf-8")
    elif fmt == "ass":
        def at(t):
            cs = int(round(t * 100))
            h, cs = divmod(cs, 360000)
            m, cs = divmod(cs, 6000)
            s, cs = divmod(cs, 100)
            return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
        head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[V4+ Styles]\n"
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
                "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
                "MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,64,&H00FFFFFF,&H000000FF,&H00000000,"
                "&H64000000,0,0,0,0,100,100,0,0,1,3,1,2,40,40,50,1\n\n[Events]\n"
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        dst.write_text(head + "\n".join(f"Dialogue: 0,{at(a)},{at(b)},Default,,0,0,0,,{t.replace(chr(10), chr(92) + 'N')}"
                                        for a, b, t in cues) + "\n", encoding="utf-8")
    else:
        raise ConversionError(f"Subtitles to .{fmt} is not supported.")
    return dst


# --------------------------------------------------------------------------- afspeellijsten

def read_playlist(path: Path) -> list[dict]:
    from .textfmt import read_text
    ext = path.suffix.lower().lstrip(".")
    text = read_text(path)
    items: list[dict] = []
    if ext in ("m3u", "m3u8", "ram"):
        title, dur = "", ""
        for line in text.splitlines():
            line = line.strip()
            m = re.match(r"#EXTINF:\s*(-?\d+)[^,]*,(.*)", line)
            if m:
                dur, title = m.group(1), m.group(2).strip()
            elif line and not line.startswith("#"):
                items.append({"location": line, "title": title, "duration": dur})
                title, dur = "", ""
    elif ext == "pls":
        entries: dict = {}
        for line in text.splitlines():
            m = re.match(r"(File|Title|Length)(\d+)=(.*)", line.strip(), re.I)
            if m:
                key = {"file": "location", "title": "title", "length": "duration"}[m.group(1).lower()]
                entries.setdefault(int(m.group(2)), {})[key] = m.group(3)
        items = [entries[k] for k in sorted(entries)]
    else:  # xspf, wpl, asx (XML)
        root = ET.fromstring(re.sub(r"<\?wpl[^>]*\?>", "", text).encode("utf-8"))
        for el in root.iter():
            tag = el.tag.split("}")[-1].lower()
            if tag == "track":
                get = {c.tag.split("}")[-1]: (c.text or "") for c in el}
                items.append({"location": get.get("location", ""), "title": get.get("title", ""),
                              "duration": str(int(get["duration"]) // 1000) if get.get("duration", "").isdigit() else ""})
            elif tag == "media" and el.get("src"):
                items.append({"location": el.get("src"), "title": "", "duration": ""})
            elif tag == "entry":
                ref = next((c for c in el if c.tag.lower().endswith("ref")), None)
                title = next((c.text for c in el if c.tag.lower().endswith("title")), "")
                if ref is not None:
                    items.append({"location": ref.get("href") or ref.get("HREF") or "", "title": title or "",
                                  "duration": ""})
    if not items:
        raise ConversionError("No tracks found in this playlist.")
    return items


def write_playlist(items: list[dict], dst: Path, fmt: str, name: str) -> Path:
    e = html.escape
    if fmt in ("m3u", "m3u8"):
        lines = ["#EXTM3U"]
        for it in items:
            lines.append(f"#EXTINF:{it.get('duration') or -1},{it.get('title') or Path(it['location']).stem}")
            lines.append(it["location"])
        dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif fmt == "pls":
        lines = ["[playlist]"]
        for i, it in enumerate(items, 1):
            lines += [f"File{i}={it['location']}", f"Title{i}={it.get('title', '')}", f"Length{i}={it.get('duration') or -1}"]
        lines += [f"NumberOfEntries={len(items)}", "Version=2"]
        dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif fmt == "xspf":
        tracks = "".join(f"<track><location>{e(it['location'])}</location><title>{e(it.get('title', ''))}</title></track>"
                         for it in items)
        dst.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<playlist version="1" xmlns="http://xspf.org/ns/0/">'
                       f"<title>{e(name)}</title><trackList>{tracks}</trackList></playlist>\n", encoding="utf-8")
    elif fmt == "wpl":
        media = "".join(f'<media src="{e(it["location"])}"/>' for it in items)
        dst.write_text(f'<?wpl version="1.0"?>\n<smil><head><title>{e(name)}</title></head><body><seq>{media}</seq>'
                       "</body></smil>\n", encoding="utf-8")
    elif fmt == "asx":
        entries = "".join(f'<entry><title>{e(it.get("title", ""))}</title><ref href="{e(it["location"])}"/></entry>'
                          for it in items)
        dst.write_text(f'<asx version="3.0"><title>{e(name)}</title>{entries}</asx>\n', encoding="utf-8")
    elif fmt in ("csv", "txt"):
        from .datafmt import write
        write(items, dst, fmt, name)
    else:
        raise ConversionError(f"Playlist to .{fmt} is not supported.")
    return dst


# --------------------------------------------------------------------------- MIDI

def soundfont() -> Path | None:
    import os
    import sys
    cands = [os.environ.get("ANYTHING_SOUNDFONT", "")]
    cands += ["/usr/share/sounds/sf2/FluidR3_GM.sf2", "/usr/share/soundfonts/default.sf2",
              "/usr/share/sounds/sf2/default-GM.sf2", "/opt/homebrew/share/soundfonts/default.sf2",
              "/usr/local/share/soundfonts/default.sf2"]
    if sys.platform == "win32":
        cands.append(r"C:\soundfonts\default.sf2")
    for c in cands:
        if c and Path(c).is_file():
            return Path(c)
    return None


def midi_summary(path: Path) -> str:
    data = path.read_bytes()
    if data[:4] != b"MThd":
        raise ConversionError("Not a valid MIDI file.")
    fmt, ntracks, div = int.from_bytes(data[8:10], "big"), int.from_bytes(data[10:12], "big"), \
        int.from_bytes(data[12:14], "big")
    names, pos = [], 14
    while pos < len(data) - 8 and data[pos:pos + 4] == b"MTrk":
        size = int.from_bytes(data[pos + 4:pos + 8], "big")
        chunk = data[pos + 8:pos + 8 + size]
        m = re.search(rb"\xff\x03(.)", chunk, re.S)
        if m:
            n = m.group(1)[0]
            names.append(chunk[m.end():m.end() + n].decode("latin-1"))
        pos += 8 + size
    return (f"MIDI file, format {fmt}, {ntracks} tracks, {div} ticks per quarter note\n" +
            "\n".join(f"  spoor {i + 1}: {n}" for i, n in enumerate(names)))


def midi_render(src: Path, dst: Path, fmt: str) -> Path:
    if fmt == "txt":
        dst.write_text(midi_summary(src) + "\n", encoding="utf-8")
        return dst
    sf = soundfont()
    if not have("fluidsynth") or not sf:
        raise ConversionError("MIDI to audio needs FluidSynth and a SoundFont (.sf2). macOS: brew install fluid-synth · Linux: sudo apt install fluidsynth fluid-soundfont-gm · or put the path to an .sf2 in ANYTHING_SOUNDFONT.")
    wav = dst.with_suffix(".wav") if fmt != "wav" else dst
    subprocess.run(["fluidsynth", "-ni", "-g", "1.0", "-F", str(wav), "-r", "44100", str(sf), str(src)],
                   capture_output=True, timeout=1800, **NO_WINDOW)
    if not wav.exists():
        raise ConversionError("FluidSynth could not play this MIDI file.")
    if fmt != "wav":
        from .media import process
        out = process(wav, dst.parent, {"format": fmt, "quality": "high"})
        wav.unlink(missing_ok=True)
        return out
    return wav


def convert(src: Path, out_dir: Path, fmt: str, opts: dict) -> Path:
    ext = src.suffix.lower().lstrip(".")
    dst = out_dir / f"{src.stem}{'_edited' if fmt == ext else ''}.{fmt}"
    if ext in MIDI:
        return midi_render(src, dst, fmt)
    if ext in PLAYLISTS:
        return write_playlist(read_playlist(src), dst, fmt, src.stem)
    return write_cues(read_cues(src), dst, fmt)
