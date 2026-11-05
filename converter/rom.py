"""Emulatorbestanden: schijfimages en cartridge-ROMs omzetten, patches toepassen.

Schijven (PlayStation, Saturn, Sega CD, PC Engine CD, Dreamcast, PSP, ...):
  CUE/BIN (ook meerdere sporen), IMG/CCD, MDF/MDS, NRG, ISO, CSO, GDI, CHD
  - naar ISO (datatrack, 2048 bytes per sector)
  - naar één BIN + CUE (meerdere .bin-sporen samenvoegen)
  - audiosporen naar WAV
  - ISO naar BIN/CUE, ISO <-> CSO (PSP), en CHD via chdman (als dat geïnstalleerd is)
Cartridges:
  - N64: .z64 / .v64 / .n64 (bytevolgorde)
  - SNES: .smc (met 512-byte kopieerheader) <-> .sfc
  - Mega Drive: .smd (interleaved) -> .md/.bin
  - Nintendo DS: inkorten (trim) tot de echte grootte
Patches: IPS, UPS en BPS toepassen (ROM en patch samen kiezen).
Geen ontsleuteling of kopieerbeveiliging: alleen voor je eigen back-ups.
"""
from __future__ import annotations

import re
import shutil
import struct
import wave
import zipfile
import zlib
from pathlib import Path
from typing import Callable, Optional

from .util import ConversionError, run

ProgressFn = Callable[[float, str], None]

SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
SECTOR = {"AUDIO": 2352, "MODE1/2352": 2352, "MODE2/2352": 2352, "MODE1/2048": 2048, "MODE2/2336": 2336,
          "MODE2/2048": 2048, "CDG": 2448, "CDI/2352": 2352}
DISC_EXT = {"cue", "iso", "chd", "gdi", "ccd", "img", "mdf", "mds", "nrg", "cso", "toc"}
ROM_EXT = {"nes", "fds", "unf", "sfc", "smc", "fig", "swc", "z64", "n64", "v64", "gb", "gbc", "gba", "nds", "dsi",
           "smd", "gen", "32x", "sms", "gg", "sg", "pce", "a26", "a52", "a78", "lnx", "ws", "wsc", "ngp",
           "ngc", "vb", "col", "min", "vec"}
PATCH_EXT = {"ips", "ups", "bps"}
CUE_LIKE = ("cue", "gdi", "ccd", "mds")


# --------------------------------------------------------------------------- herkennen

def is_disc_bin(path: Path) -> bool:
    """.bin kan een schijfimage (CD-sectoren) of een cartridge (Mega Drive, Atari) zijn."""
    try:
        with open(path, "rb") as f:
            head = f.read(16)
        size = path.stat().st_size
    except OSError:
        return False
    return head[:12] == SYNC or (size >= 2352 * 300 and size % 2352 == 0)


def chdman() -> Optional[str]:
    found = shutil.which("chdman")
    if found:
        return found
    for cand in ("/opt/homebrew/bin/chdman", "/usr/local/bin/chdman", r"C:\Program Files\MAME\chdman.exe",
                 r"C:\MAME\chdman.exe"):
        if Path(cand).exists():
            return cand
    return None


def n64_order(data: bytes) -> Optional[str]:
    return {b"\x80\x37\x12\x40": "z64", b"\x37\x80\x40\x12": "v64", b"\x40\x12\x37\x80": "n64"}.get(data[:4])


def targets(path: Path, category: str, patches: list[Path]) -> list[str]:
    ext = path.suffix.lower().lstrip(".")
    out: list[str] = []
    if patches:
        out.append("patch")
    if category == "disc":
        if ext == "iso":
            out += ["cue", "cso", "chd"]
        elif ext == "cso":
            out += ["iso", "cue"]
        elif ext == "chd":
            out += ["cue", "iso"]
        elif ext == "gdi":
            out += ["chd"]
        elif ext == "nrg":
            out += ["iso", "cue"]
        else:  # cue, bin, img, ccd, mdf, mds
            out += ["iso", "cue", "wav", "chd", "cso"]
            if ext == "cue":  # only offer .wav when the disc really has audio tracks
                try:
                    if not any(t["type"] == "AUDIO" for f in parse_cue(path) for t in f["tracks"]):
                        out.remove("wav")
                except (ConversionError, OSError, ValueError, KeyError):
                    pass
        out += ["zip", "7z"]
        return out
    head = path.read_bytes()[:4] if path.stat().st_size >= 4 else b""
    if n64_order(head):
        out += [e for e in ("z64", "v64", "n64") if e != n64_order(head)]
    elif ext in ("smc", "sfc", "fig", "swc"):
        out += ["sfc", "smc"]
    elif ext == "smd":
        out += ["md", "bin"]
    elif ext == "nds":
        out += ["nds"]
    out += ["zip", "7z"]
    return out


# --------------------------------------------------------------------------- CUE

def _msf(s: str) -> int:
    m, sec, fr = (int(x) for x in s.split(":"))
    return (m * 60 + sec) * 75 + fr


def _fmt_msf(frames: int) -> str:
    return f"{frames // 4500:02d}:{frames // 75 % 60:02d}:{frames % 75:02d}"


def parse_cue(cue: Path) -> list[dict]:
    """[{file: Path, tracks: [{num, type, index: {nr: frames}, pregap}]}]"""
    files: list[dict] = []
    text = cue.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r'FILE\s+"?(.+?)"?\s+(BINARY|MOTOROLA|WAVE|MP3|AIFF)$', line, re.I)
        if m:
            p = cue.parent / m.group(1)
            if not p.exists():  # hoofdletters, spaties of tekens die bij uploaden zijn aangepast
                def norm(n: str) -> str:
                    return re.sub(r"[^a-z0-9.]", "", n.lower())
                want = norm(Path(m.group(1).replace("\\", "/")).name)
                cand = [x for x in cue.parent.iterdir() if norm(x.name) == want]
                if not cand:
                    raise ConversionError(f"The CUE refers to '{m.group(1)}', but that file is missing. Choose the .cue and all .bin files together (or a zip with everything).")
                p = cand[0]
            files.append({"file": p, "tracks": []})
            continue
        m = re.match(r"TRACK\s+(\d+)\s+(\S+)", line, re.I)
        if m and files:
            files[-1]["tracks"].append({"num": int(m.group(1)), "type": m.group(2).upper(), "index": {},
                                        "extra": []})
            continue
        m = re.match(r"INDEX\s+(\d+)\s+(\d+:\d+:\d+)", line, re.I)
        if m and files and files[-1]["tracks"]:
            files[-1]["tracks"][-1]["index"][int(m.group(1))] = _msf(m.group(2))
            continue
        if files and files[-1]["tracks"] and re.match(r"(PREGAP|POSTGAP|FLAGS|ISRC|TITLE|PERFORMER)\b", line, re.I):
            files[-1]["tracks"][-1]["extra"].append(line)
    if not files:
        raise ConversionError("This CUE file has no tracks.")
    return files


def _track_ranges(files: list[dict]) -> list[dict]:
    """Elk spoor met bestand, byte-begin (INDEX 01) en -einde."""
    out = []
    for f in files:
        size = f["file"].stat().st_size
        tr = f["tracks"]
        for i, t in enumerate(tr):
            ss = SECTOR.get(t["type"], 2352)
            start = t["index"].get(1, t["index"].get(0, 0)) * ss
            if i + 1 < len(tr):
                nxt = tr[i + 1]["index"]
                end = nxt.get(0, nxt.get(1, 0)) * ss
            else:
                end = size
            out.append(dict(t, file=f["file"], start=start, end=end, sector=ss))
    return out


def _data_offset(track_type: str, first_sector: bytes) -> int:
    if track_type in ("MODE1/2048", "MODE2/2048"):
        return 0
    if track_type == "MODE2/2336":
        return 8
    if track_type == "MODE1/2352":
        return 16
    if track_type in ("MODE2/2352", "CDI/2352"):
        return 24  # Mode 2 Form 1 (XA): subheader van 8 bytes
    # onbekend: kijk naar het modusbyte
    return 16 if first_sector[15:16] == b"\x01" else 24


def raw_to_iso(src: Path, start: int, end: int, sector: int, ttype: str, dst: Path,
               progress: Optional[ProgressFn] = None) -> Path:
    with open(src, "rb") as f, open(dst, "wb") as o:
        f.seek(start)
        first = f.read(sector)
        off = _data_offset(ttype, first)
        f.seek(start)
        total = max(1, (end - start) // sector)
        for n in range(total):
            sec = f.read(sector)
            if len(sec) < off + 2048:
                break
            o.write(sec[off:off + 2048])
            if progress and n % 4096 == 0:
                progress(0.1 + 0.85 * n / total, "to ISO")
    return dst


def cue_to_iso(cue: Path, out_dir: Path, progress=None) -> Path:
    tracks = _track_ranges(parse_cue(cue))
    data = next((t for t in tracks if t["type"] != "AUDIO"), None)
    if not data:
        raise ConversionError("This disc only has audio tracks; choose .wav.")
    dst = out_dir / f"{cue.stem}.iso"
    raw_to_iso(data["file"], data["start"], data["end"], data["sector"], data["type"], dst, progress)
    return dst


def merge_cue(cue: Path, out_dir: Path, progress=None) -> tuple[Path, Path]:
    """Alle sporen in één .bin, met een nieuwe .cue (zoals binmerge)."""
    files = parse_cue(cue)
    work = out_dir / "_disc"
    work.mkdir(exist_ok=True)
    bin_out = work / f"{cue.stem}.bin"
    lines = [f'FILE "{bin_out.name}" BINARY']
    offset_frames = 0
    with open(bin_out, "wb") as o:
        for k, f in enumerate(files):
            for t in f["tracks"]:
                lines.append(f"  TRACK {t['num']:02d} {t['type']}")
                lines += [f"    {x}" for x in t["extra"]]
                for nr, frames in sorted(t["index"].items()):
                    lines.append(f"    INDEX {nr:02d} {_fmt_msf(offset_frames + frames)}")
            with open(f["file"], "rb") as src:
                shutil.copyfileobj(src, o, 1 << 20)
            ss = SECTOR.get(f["tracks"][0]["type"], 2352) if f["tracks"] else 2352
            offset_frames += f["file"].stat().st_size // ss
            if progress:
                progress(0.1 + 0.8 * (k + 1) / len(files), "merging tracks")
    cue_out = work / f"{cue.stem}.cue"
    cue_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return cue_out, bin_out


def audio_tracks(cue: Path, out_dir: Path, progress=None) -> Path:
    tracks = [t for t in _track_ranges(parse_cue(cue)) if t["type"] == "AUDIO"]
    if not tracks:
        raise ConversionError("This disc has no audio tracks.")
    dst = out_dir / f"{cue.stem}_audio.zip"
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for k, t in enumerate(tracks):
            tmp = out_dir / f"spoor{t['num']:02d}.wav"
            with open(t["file"], "rb") as f, wave.open(str(tmp), "wb") as w:
                w.setnchannels(2)
                w.setsampwidth(2)
                w.setframerate(44100)
                f.seek(t["start"])
                left = t["end"] - t["start"]
                while left > 0:
                    chunk = f.read(min(left, 2352 * 1000))
                    if not chunk:
                        break
                    w.writeframes(chunk)
                    left -= len(chunk)
            z.write(tmp, f"{cue.stem} - spoor {t['num']:02d}.wav")
            tmp.unlink()
            if progress:
                progress(0.1 + 0.85 * (k + 1) / len(tracks), f"spoor {t['num']}")
    return dst


def bin_cue_for(src: Path) -> Path:
    """Losse .bin/.img/.mdf zonder (bruikbare) cue: één dataspoor aannemen."""
    with open(src, "rb") as f:
        head = f.read(16)
    size = src.stat().st_size
    if head[:12] == SYNC:
        if size % 2448 == 0 and size % 2352 != 0:
            mode = "MODE1/2352" if head[15] == 1 else "MODE2/2352"  # met subkanaal (MDF): zelfde modus
        else:
            mode = "MODE1/2352" if head[15] == 1 else "MODE2/2352"
    elif size % 2048 == 0:
        mode = "MODE1/2048"
    else:
        mode = "MODE1/2352"
    cue = src.with_suffix(".cue")
    if cue.exists():
        cue = src.parent / f"{src.stem}_created.cue"
    cue.write_text(f'FILE "{src.name}" BINARY\n  TRACK 01 {mode}\n    INDEX 01 00:00:00\n', encoding="utf-8")
    return cue


def ccd_cue(ccd: Path) -> Path:
    """CloneCD (.ccd + .img): een .cue maken uit de spoorinformatie."""
    img = next((p for p in ccd.parent.iterdir() if p.stem.lower() == ccd.stem.lower()
                and p.suffix.lower() == ".img"), None)
    if not img:
        raise ConversionError("The .img file for this .ccd is missing; choose them together.")
    text = ccd.read_text(errors="replace")
    lines = [f'FILE "{img.name}" BINARY']
    for sec in re.finditer(r"\[TRACK (\d+)\]([^\[]*)", text):
        num = int(sec.group(1))
        mode = int(re.search(r"MODE=(\d)", sec.group(2)).group(1)) if re.search(r"MODE=(\d)", sec.group(2)) else 1
        ttype = {0: "AUDIO", 1: "MODE1/2352", 2: "MODE2/2352"}.get(mode, "MODE1/2352")
        lines.append(f"  TRACK {num:02d} {ttype}")
        for m in re.finditer(r"INDEX (\d)=(\d+)", sec.group(2)):
            lines.append(f"    INDEX {int(m.group(1)):02d} {_fmt_msf(int(m.group(2)))}")
    if len(lines) == 1:
        return bin_cue_for(img)
    cue = ccd.with_suffix(".cue")
    cue.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return cue


def nrg_to_iso(src: Path, out_dir: Path) -> Path:
    data_end = src.stat().st_size
    with open(src, "rb") as f:
        f.seek(-12, 2)
        tail = f.read(12)
        if tail[:4] == b"NER5":
            data_end = struct.unpack(">Q", tail[4:])[0]
        elif tail[4:8] == b"NERO":
            data_end = struct.unpack(">I", tail[8:])[0]
        f.seek(0)
        head = f.read(16)
    dst = out_dir / f"{src.stem}.iso"
    if head[:12] == SYNC:
        return raw_to_iso(src, 0, data_end, 2352, "", dst)
    # Nero zet vaak 150 sectoren (300 KB) pregap vooraan
    start = 0
    with open(src, "rb") as f:
        f.seek(16 * 2048)
        if f.read(6)[1:6] != b"CD001":
            f.seek(150 * 2048 + 16 * 2048)
            if f.read(6)[1:6] == b"CD001":
                start = 150 * 2048
    with open(src, "rb") as f, open(dst, "wb") as o:
        f.seek(start)
        left = data_end - start
        while left > 0:
            chunk = f.read(min(left, 1 << 20))
            if not chunk:
                break
            o.write(chunk)
            left -= len(chunk)
    return dst


# --------------------------------------------------------------------------- CSO (PSP)

def iso_to_cso(src: Path, dst: Path, level: int = 9, progress=None) -> Path:
    block = 2048
    total = src.stat().st_size
    nblocks = (total + block - 1) // block
    index = []
    with open(src, "rb") as f, open(dst, "wb") as o:
        o.write(b"CISO" + struct.pack("<IQIBBH", 0x18, total, block, 1, 0, 0))
        o.write(b"\0" * 4 * (nblocks + 1))
        pos = 0x18 + 4 * (nblocks + 1)
        for n in range(nblocks):
            raw = f.read(block)
            comp = zlib.compressobj(level, zlib.DEFLATED, -15)
            data = comp.compress(raw) + comp.flush()
            if len(data) >= len(raw):
                index.append(pos | 0x80000000)
                data = raw
            else:
                index.append(pos)
            o.write(data)
            pos += len(data)
            if progress and n % 8192 == 0:
                progress(0.1 + 0.85 * n / nblocks, "compressing to CSO")
        index.append(pos)
        if pos >= 0x80000000:
            raise ConversionError("This image is too large for CSO (max. ~2 GB compressed).")
        o.seek(0x18)
        o.write(struct.pack(f"<{len(index)}I", *index))
    return dst


def cso_to_iso(src: Path, dst: Path, progress=None) -> Path:
    with open(src, "rb") as f, open(dst, "wb") as o:
        head = f.read(0x18)
        if head[:4] != b"CISO":
            raise ConversionError("This is not a CSO file (ZSO is not supported).")
        _, hsize, total, block, ver, align, _ = struct.unpack("<4sIQIBBH", head)
        nblocks = (total + block - 1) // block
        index = struct.unpack(f"<{nblocks + 1}I", f.read(4 * (nblocks + 1)))
        for n in range(nblocks):
            plain = index[n] & 0x80000000
            a = (index[n] & 0x7FFFFFFF) << align
            b = (index[n + 1] & 0x7FFFFFFF) << align
            f.seek(a)
            data = f.read(b - a)
            o.write(data[:block] if plain else zlib.decompress(data, -15, block))
            if progress and n % 8192 == 0:
                progress(0.1 + 0.85 * n / nblocks, "uitpakken")
        o.truncate(total)
    return dst


def iso_to_cue(iso: Path, out_dir: Path) -> tuple[Path, Path]:
    work = out_dir / "_disc"
    work.mkdir(exist_ok=True)
    bin_out = work / f"{iso.stem}.bin"
    shutil.copyfile(iso, bin_out)
    cue = work / f"{iso.stem}.cue"
    cue.write_text(f'FILE "{bin_out.name}" BINARY\n  TRACK 01 MODE1/2048\n    INDEX 01 00:00:00\n', encoding="utf-8")
    return cue, bin_out


# --------------------------------------------------------------------------- CHD (chdman)

def _chd(args: list[str]) -> None:
    tool = chdman()
    if not tool:
        raise ConversionError("CHD needs chdman (from MAME). macOS: brew install rom-tools · Ubuntu/Debian: sudo apt install mame-tools · Windows: chdman.exe from MAME.")
    run([tool, *args, "-f"], timeout=7200)


# --------------------------------------------------------------------------- cartridges

def n64_convert(data: bytes, want: str) -> bytes:
    have = n64_order(data)
    if not have:
        raise ConversionError("This is not a recognisable N64 ROM.")
    if have == want:
        return data
    # eerst naar z64 (big endian)
    if have == "v64":
        z = bytearray(data)
        z[0::2], z[1::2] = data[1::2], data[0::2]
    elif have == "n64":
        z = bytearray(len(data))
        z[0::4], z[1::4], z[2::4], z[3::4] = data[3::4], data[2::4], data[1::4], data[0::4]
    else:
        z = bytearray(data)
    if want == "z64":
        return bytes(z)
    out = bytearray(len(z))
    if want == "v64":
        out[0::2], out[1::2] = z[1::2], z[0::2]
    else:
        out[0::4], out[1::4], out[2::4], out[3::4] = z[3::4], z[2::4], z[1::4], z[0::4]
    return bytes(out)


def smd_to_bin(data: bytes) -> bytes:
    if len(data) % 16384 == 512:
        data = data[512:]
    out = bytearray(len(data))
    for b in range(0, len(data), 16384):
        blk = data[b:b + 16384]
        half = len(blk) // 2
        out[b + 1:b + len(blk):2] = blk[:half]
        out[b:b + len(blk):2] = blk[half:half * 2]
    return bytes(out)


def nds_trim(data: bytes) -> bytes:
    if len(data) < 0x200:
        raise ConversionError("This is not a valid Nintendo DS ROM.")
    used = struct.unpack_from("<I", data, 0x80)[0]
    # DSi-ROM's hebben een groter gebruikt gebied (0x210)
    if data[0x12] & 0x02 and len(data) >= 0x214:
        used = max(used, struct.unpack_from("<I", data, 0x210)[0])
    # RSA-handtekening (0x88 bytes) direct na het gebruikte deel behouden
    if data[used:used + 2] == b"ac":
        used += 0x88
    if not 0x200 < used <= len(data):
        raise ConversionError("The DS header gives an illogical size; not trimmed.")
    return data[:used]


# --------------------------------------------------------------------------- patches

def _vlq(data: bytes, pos: int) -> tuple[int, int]:
    """Getal zoals in UPS/BPS (7 bits per byte, met +1 per vervolg)."""
    value, shift = 0, 1
    while True:
        x = data[pos]
        pos += 1
        value += (x & 0x7F) * shift
        if x & 0x80:
            return value, pos
        shift <<= 7
        value += shift


def apply_ips(rom: bytes, patch: bytes) -> bytes:
    if patch[:5] != b"PATCH":
        raise ConversionError("Ongeldige IPS-patch.")
    out = bytearray(rom)
    pos = 5
    while pos + 3 <= len(patch):
        if patch[pos:pos + 3] == b"EOF":
            pos += 3
            if pos + 3 <= len(patch):  # optionele inkorting
                out = out[:int.from_bytes(patch[pos:pos + 3], "big")]
            break
        off = int.from_bytes(patch[pos:pos + 3], "big")
        size = int.from_bytes(patch[pos + 3:pos + 5], "big")
        pos += 5
        if size:
            chunk = patch[pos:pos + size]
            pos += size
        else:  # RLE
            run_len = int.from_bytes(patch[pos:pos + 2], "big")
            chunk = patch[pos + 2:pos + 3] * run_len
            pos += 3
        if off + len(chunk) > len(out):
            out.extend(b"\0" * (off + len(chunk) - len(out)))
        out[off:off + len(chunk)] = chunk
    return bytes(out)


def apply_ups(rom: bytes, patch: bytes) -> bytes:
    if patch[:4] != b"UPS1":
        raise ConversionError("Ongeldige UPS-patch.")
    pos = 4
    in_size, pos = _vlq(patch, pos)
    out_size, pos = _vlq(patch, pos)
    src_crc, dst_crc = struct.unpack_from("<II", patch, len(patch) - 12)
    if zlib.crc32(rom) != src_crc:
        raise ConversionError("This UPS patch belongs to a different version of the ROM (CRC mismatch).")
    out = bytearray(rom[:out_size].ljust(out_size, b"\0"))
    rel = 0
    end = len(patch) - 12
    while pos < end:
        skip, pos = _vlq(patch, pos)
        rel += skip
        while True:
            x = patch[pos]
            pos += 1
            if rel < out_size:
                out[rel] = (rom[rel] if rel < len(rom) else 0) ^ x
            rel += 1
            if x == 0:
                break
    if zlib.crc32(out) != dst_crc:
        raise ConversionError("Patch applied, but the check (CRC) does not match.")
    return bytes(out)


def apply_bps(rom: bytes, patch: bytes) -> bytes:
    if patch[:4] != b"BPS1":
        raise ConversionError("Ongeldige BPS-patch.")
    src_crc, dst_crc, _ = struct.unpack_from("<III", patch, len(patch) - 12)
    if zlib.crc32(rom) != src_crc:
        raise ConversionError("This BPS patch belongs to a different version of the ROM (CRC mismatch).")
    pos = 4
    _, pos = _vlq(patch, pos)
    out_size, pos = _vlq(patch, pos)
    meta, pos = _vlq(patch, pos)
    pos += meta
    out = bytearray(out_size)
    op = src_rel = dst_rel = 0
    end = len(patch) - 12
    while pos < end:
        data, pos = _vlq(patch, pos)
        cmd, length = data & 3, (data >> 2) + 1
        if cmd == 0:  # SourceRead
            out[op:op + length] = rom[op:op + length]
            op += length
        elif cmd == 1:  # TargetRead
            out[op:op + length] = patch[pos:pos + length]
            pos += length
            op += length
        else:
            d, pos = _vlq(patch, pos)
            delta = -(d >> 1) if d & 1 else d >> 1
            if cmd == 2:  # SourceCopy
                src_rel += delta
                out[op:op + length] = rom[src_rel:src_rel + length]
                src_rel += length
                op += length
            else:  # TargetCopy (mag overlappen)
                dst_rel += delta
                for _ in range(length):
                    out[op] = out[dst_rel]
                    op += 1
                    dst_rel += 1
    if zlib.crc32(out) != dst_crc:
        raise ConversionError("Patch applied, but the check (CRC) does not match.")
    return bytes(out)


# --------------------------------------------------------------------------- hoofdfunctie

def _zip(files: list[Path], dst: Path) -> Path:
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.name)
    return dst


def disc_files(src: Path) -> list[Path]:
    """Alle bestanden die bij deze schijf horen (cue + bins, gdi + sporen, ...)."""
    ext = src.suffix.lower().lstrip(".")
    if ext == "cue":
        return [src] + [f["file"] for f in parse_cue(src)]
    if ext in ("gdi", "ccd", "mds"):
        return [p for p in src.parent.iterdir() if p.is_file() and not p.name.startswith(".")]
    return [src]


def process(src: Path, out_dir: Path, category: str, opts: dict, progress: Optional[ProgressFn] = None) -> Path:
    fmt = (opts.get("format") or "").lower()
    ext = src.suffix.lower().lstrip(".")
    stem = src.stem
    if progress:
        progress(0.05, "lezen")

    if fmt == "patch":
        patch = Path(opts["patch"]) if opts.get("patch") else \
            next((p for p in src.parent.iterdir() if p.suffix.lower().lstrip(".") in PATCH_EXT), None)
        if not patch:
            raise ConversionError("No patch (.ips, .ups or .bps) found; choose the ROM and the patch together.")
        kind = patch.suffix.lower().lstrip(".")
        data = {"ips": apply_ips, "ups": apply_ups, "bps": apply_bps}[kind](src.read_bytes(), patch.read_bytes())
        dst = out_dir / f"{stem} [{patch.stem}].{ext}"
        dst.write_bytes(data)
        return dst

    if fmt in ("zip", "7z"):
        files = disc_files(src) if category == "disc" else [src]
        if fmt == "zip":
            return _zip(files, out_dir / f"{stem}.zip")
        from .archive import _pack
        dst = out_dir / f"{stem}.7z"
        _pack(files, src.parent, dst, "7z", 9)
        return dst

    if category == "rom":
        data = src.read_bytes()
        if fmt in ("z64", "v64", "n64"):
            out = n64_convert(data, fmt)
        elif fmt == "sfc":
            out = data[512:] if len(data) % 1024 == 512 else data
        elif fmt == "smc":
            out = data if len(data) % 1024 == 512 else b"\0" * 512 + data
        elif fmt in ("md", "bin") and ext == "smd":
            out = smd_to_bin(data)
        elif fmt == "nds":
            out = nds_trim(data)
            stem += "_trim"
        else:
            raise ConversionError(f"ROM to .{fmt} is not supported.")
        dst = out_dir / f"{stem}{'_edited' if fmt == ext and fmt != 'nds' else ''}.{fmt}"
        dst.write_bytes(out)
        return dst

    # ---- schijven: eerst een bruikbare .cue zoeken/maken
    def as_cue() -> Path:
        if ext == "cue":
            return src
        if ext == "ccd":
            return ccd_cue(src)
        if ext == "mds":
            mdf = next((p for p in src.parent.iterdir() if p.suffix.lower() == ".mdf"), None)
            if not mdf:
                raise ConversionError("The .mdf file for this .mds is missing; choose them together.")
            return bin_cue_for(mdf)
        if ext == "nrg":
            return bin_cue_for(nrg_to_iso(src, out_dir))
        return bin_cue_for(src)

    if ext == "chd":
        if fmt == "iso":
            cue = out_dir / f"{stem}.cue"
            _chd(["extractcd", "-i", str(src), "-o", str(cue), "-ob", str(out_dir / f"{stem}.bin")])
            return cue_to_iso(cue, out_dir, progress)
        if fmt == "cue":
            work = out_dir / "_disc"
            work.mkdir(exist_ok=True)
            cue = work / f"{stem}.cue"
            _chd(["extractcd", "-i", str(src), "-o", str(cue), "-ob", str(work / f"{stem}.bin")])
            return _zip(disc_files(cue), out_dir / f"{stem} (bin-cue).zip")
        raise ConversionError(f"CHD to .{fmt} is not supported.")
    if ext == "cso":
        iso = cso_to_iso(src, out_dir / f"{stem}.iso", progress)
        if fmt == "iso":
            return iso
        cue, bin_ = iso_to_cue(iso, out_dir)
        return _zip([cue, bin_], out_dir / f"{stem} (bin-cue).zip")
    if ext == "iso":
        if fmt == "cso":
            return iso_to_cso(src, out_dir / f"{stem}.cso", progress=progress)
        if fmt == "cue":
            cue, bin_ = iso_to_cue(src, out_dir)
            return _zip([cue, bin_], out_dir / f"{stem} (bin-cue).zip")
        if fmt == "chd":
            dst = out_dir / f"{stem}.chd"
            _chd(["createcd", "-i", str(src), "-o", str(dst)])
            return dst
        raise ConversionError(f"ISO to .{fmt} is not supported.")
    if ext == "gdi" and fmt == "chd":
        dst = out_dir / f"{stem}.chd"
        _chd(["createcd", "-i", str(src), "-o", str(dst)])
        return dst

    cue = as_cue()
    if fmt == "iso":
        return cue_to_iso(cue, out_dir, progress)
    if fmt == "cue":
        new_cue, new_bin = merge_cue(cue, out_dir, progress)
        return _zip([new_cue, new_bin], out_dir / f"{stem} (bin-cue).zip")
    if fmt == "wav":
        return audio_tracks(cue, out_dir, progress)
    if fmt == "chd":
        dst = out_dir / f"{stem}.chd"
        _chd(["createcd", "-i", str(cue), "-o", str(dst)])
        return dst
    if fmt == "cso":
        iso = cue_to_iso(cue, out_dir, progress)
        return iso_to_cso(iso, out_dir / f"{stem}.cso", progress=progress)
    raise ConversionError(f"Disc image to .{fmt} is not supported.")
