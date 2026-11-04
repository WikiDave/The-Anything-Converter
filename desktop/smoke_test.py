"""Rooktest voor de gebouwde desktop-app (draait in de GitHub-workflow).

Start het programma, wacht tot /api/ping antwoordt, converteert een afbeelding (Pillow) en een
geluidsfragment (meegeleverde ffmpeg), en sluit de app weer af via /api/quit.

Gebruik: python desktop/smoke_test.py <pad-naar-AnythingConverter(.exe)>
"""
from __future__ import annotations

import io
import json
import math
import os
import struct
import subprocess
import sys
import time
import urllib.request
import uuid
import wave

BASE = "http://127.0.0.1:8737"


def call(path, data=None, files=None):
    headers, body = {}, None
    if files:
        boundary = uuid.uuid4().hex
        name, blob = files
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n").encode() + blob + f"\r\n--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def convert(name, blob, fmt):
    up = call("/api/upload", files=(name, blob))
    job = call("/api/convert", {"id": up["id"], "options": {"format": fmt, "quality": "medium"}})
    for _ in range(120):
        job = call("/api/job/" + job["id"])
        if job["status"] in ("done", "error"):
            break
        time.sleep(1)
    assert job["status"] == "done", f"{name} -> {fmt} mislukt: {job.get('error')}"
    print(f"  ok: {name} -> {job['filename']} ({job['size']} bytes)")


def sample_png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (320, 200), (40, 200, 90)).save(buf, "PNG")
    return buf.getvalue()


def sample_wav():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 44100)))
                               for i in range(44100)))
    return buf.getvalue()


def main():
    exe = sys.argv[1]
    env = dict(os.environ, BROWSER="geen-browser")  # niet echt een browser openen
    proc = subprocess.Popen([exe], env=env)
    try:
        for _ in range(90):
            try:
                info = call("/api/ping")
                break
            except Exception:
                time.sleep(1)
        else:
            raise SystemExit("app startte niet binnen 90 seconden")
        print("ping:", info)
        assert info["desktop"] is True
        convert("test.png", sample_png(), "jpg")
        convert("test.wav", sample_wav(), "mp3")
        # libtorrent aanwezig? Een kapot .torrent-bestand moet "geen geldig" geven, niet "vereisen libtorrent".
        job = call("/api/torrent", files=("kapot.torrent", b"geen torrent"))
        for _ in range(30):
            job = call("/api/job/" + job["id"])
            if job["status"] in ("done", "error"):
                break
            time.sleep(1)
        assert "geldig" in (job.get("error") or ""), f"torrent-module werkt niet: {job.get('error')}"
        print("  ok: libtorrent aanwezig")
        call("/api/quit", {})
        proc.wait(timeout=30)
        print("afgesloten met code", proc.returncode)
    finally:
        if proc.poll() is None:
            proc.kill()


if __name__ == "__main__":
    main()
