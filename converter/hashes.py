"""Checksums (hash) van een bestand: MD5, SHA-familie, CRC-32, Adler-32 en meer, optioneel als HMAC."""
from __future__ import annotations

import hashlib
import hmac
import zlib
from pathlib import Path

LABELS = {
    "crc32": "CRC-32", "adler32": "Adler-32", "md4": "MD4", "md5": "MD5", "ripemd160": "RIPEMD-160",
    "sha1": "SHA-1", "sha224": "SHA-224", "sha256": "SHA-256", "sha384": "SHA-384", "sha512": "SHA-512",
    "sha3_256": "SHA3-256", "sha3_512": "SHA3-512", "blake2b": "BLAKE2b", "blake2s": "BLAKE2s",
    "whirlpool": "Whirlpool", "sm3": "SM3",
}


def _new(name: str, key: bytes | None):
    """hashlib-object (of HMAC); valt voor MD4/RIPEMD-160 terug op pycryptodome."""
    try:
        hashlib.new(name)
        ctor = lambda d=b"": hashlib.new(name, d)  # noqa: E731
    except (ValueError, TypeError):
        try:
            from Cryptodome.Hash import MD4, RIPEMD160
        except ImportError:
            return None
        mod = {"md4": MD4, "ripemd160": RIPEMD160}.get(name)
        if not mod:
            return None

        class _W:
            def __init__(self, d=b""):
                self.h = mod.new(d)
                self.digest_size = mod.digest_size
                self.block_size = getattr(mod, "block_size", 64)

            def update(self, d):
                self.h.update(d)

            def copy(self):
                c = _W()
                c.h = self.h.copy()
                return c

            def digest(self):
                return self.h.digest()

            def hexdigest(self):
                return self.h.hexdigest()

        ctor = _W
    if key is not None:
        return hmac.new(key, digestmod=ctor)
    return ctor()


def compute(path: Path, key: str | None = None) -> dict[str, str]:
    kb = key.encode() if key else None
    objs = {n: o for n in LABELS if n not in ("crc32", "adler32") and (o := _new(n, kb)) is not None}
    crc, adler = 0, 1
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
            adler = zlib.adler32(chunk, adler)
            for o in objs.values():
                o.update(chunk)
    out = {} if kb else {"crc32": f"{crc:08x}", "adler32": f"{adler:08x}"}
    out.update({n: o.hexdigest() for n, o in objs.items()})
    return {LABELS[n]: v for n, v in sorted(out.items(), key=lambda kv: list(LABELS).index(kv[0]))}
