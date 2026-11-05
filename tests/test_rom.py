"""Emulatorbestanden: CUE/BIN, ISO, CSO, N64/SNES/Mega Drive/DS, IPS/UPS/BPS-patches."""
import io
import struct
import zipfile
import zlib

import pytest

from converter import rom
from converter.detect import detect


def mode1_sector(lba: int, payload: bytes) -> bytes:
    return rom.SYNC + bytes([0, 2, 0, 1]) + payload.ljust(2048, b"\0") + b"\0" * 288


def make_disc(folder, name="Spel (Disc 1)"):
    data = b"".join(mode1_sector(i, (b"\x01CD001" if i == 16 else b"") + f"sector {i}".encode()) for i in range(40))
    audio = bytes(range(256)) * (2352 * 10 // 256 + 1)
    audio = audio[:2352 * 10]
    (folder / f"{name} (Track 1).bin").write_bytes(data)
    (folder / f"{name} (Track 2).bin").write_bytes(audio)
    cue = folder / f"{name}.cue"
    cue.write_text(f'FILE "{name} (Track 1).bin" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n'
                   f'FILE "{name} (Track 2).bin" BINARY\n  TRACK 02 AUDIO\n    INDEX 00 00:00:00\n'
                   f'    INDEX 01 00:00:02\n')
    return cue, data, audio


def test_cue_bin_conversions(tmp_path):
    cue, data, audio = make_disc(tmp_path)
    assert detect(cue) == "disc" and detect(tmp_path / "Spel (Disc 1) (Track 1).bin") == "disc"
    out = tmp_path / "uit"
    out.mkdir()
    iso = rom.process(cue, out, "disc", {"format": "iso"})
    assert iso.stat().st_size == 40 * 2048
    assert iso.read_bytes()[16 * 2048:16 * 2048 + 6] == b"\x01CD001"
    merged = rom.process(cue, out, "disc", {"format": "cue"})
    z = zipfile.ZipFile(merged)
    names = z.namelist()
    assert len(names) == 2
    bin_name = next(n for n in names if n.endswith(".bin"))
    assert z.read(bin_name) == data + audio
    new_cue = z.read(next(n for n in names if n.endswith(".cue"))).decode()
    assert "INDEX 01 00:00:42" in new_cue and new_cue.count("FILE") == 1  # 40 sectoren + 2 frames
    wavs = zipfile.ZipFile(rom.process(cue, out, "disc", {"format": "wav"})).namelist()
    assert wavs == ["Spel (Disc 1) - spoor 02.wav"]


def test_iso_cso_roundtrip(tmp_path):
    iso = tmp_path / "game.iso"
    iso.write_bytes(b"PSP GAME" * 2048 + bytes(range(256)) * 64 + b"\0" * 5000)
    cso = rom.iso_to_cso(iso, tmp_path / "game.cso")
    assert cso.stat().st_size < iso.stat().st_size
    back = rom.cso_to_iso(cso, tmp_path / "terug.iso")
    assert back.read_bytes() == iso.read_bytes()


def test_n64_byte_orders(tmp_path):
    z64 = b"\x80\x37\x12\x40" + bytes(range(60))
    v64 = rom.n64_convert(z64, "v64")
    n64 = rom.n64_convert(z64, "n64")
    assert v64[:4] == b"\x37\x80\x40\x12" and n64[:4] == b"\x40\x12\x37\x80"
    assert rom.n64_convert(v64, "z64") == z64 and rom.n64_convert(n64, "z64") == z64
    p = tmp_path / "mario.n64"
    p.write_bytes(n64)
    assert detect(p) == "rom" and rom.targets(p, "rom", [])[:2] == ["z64", "v64"]


def test_snes_header_and_smd(tmp_path):
    p = tmp_path / "zelda.smc"
    p.write_bytes(b"H" * 512 + b"R" * 1024 * 4)
    out = rom.process(p, tmp_path, "rom", {"format": "sfc"})
    assert out.read_bytes() == b"R" * 4096
    blk = bytes(range(256)) * 64  # 16 KB
    smd = tmp_path / "sonic.smd"
    smd.write_bytes(b"\0" * 512 + blk)
    plain = rom.process(smd, tmp_path, "rom", {"format": "md"}).read_bytes()
    assert plain[1::2] == blk[:8192] and plain[0::2] == blk[8192:]


def test_nds_trim(tmp_path):
    data = bytearray(0x4000)
    struct.pack_into("<I", data, 0x80, 0x1000)
    p = tmp_path / "spel.nds"
    p.write_bytes(bytes(data))
    out = rom.process(p, tmp_path, "rom", {"format": "nds"})
    assert out.stat().st_size == 0x1000 and out.name == "spel_trim.nds"


def vlq(n):
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def test_patches(tmp_path):
    src = bytes(range(200))
    want = bytearray(src)
    want[10:13] = b"ABC"
    want = bytes(want) + b"XYZ"
    ips = b"PATCH" + (10).to_bytes(3, "big") + (3).to_bytes(2, "big") + b"ABC" + \
        (200).to_bytes(3, "big") + (3).to_bytes(2, "big") + b"XYZ" + b"EOF"
    assert rom.apply_ips(src, ips) == want
    # BPS: alles als TargetRead
    body = b"BPS1" + vlq(len(src)) + vlq(len(want)) + vlq(0) + vlq(((len(want) - 1) << 2) | 1) + want
    body += struct.pack("<II", zlib.crc32(src), zlib.crc32(want))
    bps = body + struct.pack("<I", zlib.crc32(body))
    assert rom.apply_bps(src, bps) == want
    # UPS: XOR-verschillen
    padded = src + b"\0" * 3
    ups = bytearray(b"UPS1" + vlq(len(src)) + vlq(len(want)))
    rel = 0
    i = 0
    while i < len(want):
        if want[i] == padded[i]:
            i += 1
            continue
        ups += vlq(i - rel)
        while i < len(want) and want[i] != padded[i]:
            ups.append(want[i] ^ padded[i])
            i += 1
        ups.append(0)
        i += 1
        rel = i
    ups += struct.pack("<II", zlib.crc32(src), zlib.crc32(want))
    ups += struct.pack("<I", zlib.crc32(bytes(ups)))
    assert rom.apply_ups(src, bytes(ups)) == want
    with pytest.raises(Exception, match="different version"):
        rom.apply_bps(b"anders", bps)


def test_upload_cue_and_bins_together():
    import app as server
    import tempfile
    from pathlib import Path
    d = Path(tempfile.mkdtemp())
    cue, _, _ = make_disc(d)
    files = [(open(p, "rb"), p.name) for p in sorted(d.iterdir())]
    r = server.app.test_client().post("/api/upload", data={"file": files}, content_type="multipart/form-data")
    j = r.get_json()
    assert j["category"] == "disc" and j["name"].endswith(".cue"), j
    assert "iso" in j["targets"] and len(j["info"]["files"]) == 2
    # en als zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for p in d.iterdir():
            z.write(p, p.name)
    buf.seek(0)
    j = server.app.test_client().post("/api/upload", data={"file": (buf, "spel.zip")}).get_json()
    assert j["category"] == "disc" and j["name"].endswith(".cue")


def test_upload_rom_with_patch():
    import app as server
    src = bytes(range(200))
    ips = b"PATCH" + (0).to_bytes(3, "big") + (2).to_bytes(2, "big") + b"OK" + b"EOF"
    j = server.app.test_client().post("/api/upload", data={"file": [(io.BytesIO(src), "game.gba"),
                                                                    (io.BytesIO(ips), "vertaling.ips")]},
                                      content_type="multipart/form-data").get_json()
    assert j["category"] == "rom" and j["targets"][0] == "patch"
    from converter.jobs import run_conversion
    up = server.uploads[j["id"]]["path"]
    (up.parent / "o").mkdir()
    out = run_conversion(up, up.parent / "o", "rom", {"format": "patch"})
    assert out.read_bytes()[:2] == b"OK" and "vertaling" in out.name
