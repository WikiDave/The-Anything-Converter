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
    assert job["status"] == "done", f"{name} -> {fmt} failed: {job.get('error')}"
    print(f"  ok: {name} -> {job['filename']} ({job['size']} bytes)")


def sample_png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (320, 200), (40, 200, 90)).save(buf, "PNG")
    return buf.getvalue()


def sample_pdf():
    import fitz
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Anything Converter rooktest", fontsize=18)
    return doc.tobytes()


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
            raise SystemExit("app did not start within 90 seconds")
        print("ping:", info)
        assert info["desktop"] is True
        want = os.environ.get("EXPECT_WINDOW")
        print("  venster:", info.get("window"))
        if want:
            assert info.get("window") == want, f"verwacht venster '{want}', kreeg '{info.get('window')}'"
        convert("test.png", sample_png(), "jpg")
        caps = call("/api/capabilities")
        print("  mogelijkheden:", caps)
        assert caps["pymupdf"] and caps["sevenzip"], "PDF tools or 7z missing"
        # Intel-Macs: pywhispercpp heeft daar alleen een oude versie; spraak is daar optioneel
        if not caps["speech"]:
            print("  NOTE: speech recognition not available:", caps.get("speech_error"))
            assert os.environ.get("ALLOW_NO_SPEECH") == "1", "speech recognition is missing"
        convert("test.pdf", sample_pdf(), "docx")
        convert("test.pdf", sample_pdf(), "xlsx")
        convert("test.png", sample_png(), "svg")
        # nieuwe formaten uit de catalogus (zonder extra programma's)
        convert("test.json", b'{"naam": "Anna", "lijst": [1, 2]}', "yaml")
        convert("test.srt", b"1\n00:00:01,000 --> 00:00:02,000\nHallo\n", "vtt")
        convert("test.gpx", b"<?xml version='1.0'?><gpx version='1.1' xmlns='http://www.topografix.com/GPX/1/1'>"
                b"<trk><trkseg><trkpt lat='52.1' lon='5.1'/><trkpt lat='52.2' lon='5.2'/></trkseg></trk></gpx>", "kml")
        convert("test.svg", b"<svg xmlns='http://www.w3.org/2000/svg' width='40' height='20'>"
                b"<rect width='40' height='20' fill='red'/></svg>", "png")
        convert("test.py", b"print('hallo')\n", "html")
        assert caps.get("sevenzip_tool"), "7-Zip is missing from the app"
        convert("test.wav", sample_wav(), "mp3")
        # libtorrent aanwezig? Een kapot .torrent-bestand moet "geen geldig" geven, niet "vereisen libtorrent".
        job = call("/api/torrent", files=("kapot.torrent", b"geen torrent"))
        for _ in range(30):
            job = call("/api/job/" + job["id"])
            if job["status"] in ("done", "error"):
                break
            time.sleep(1)
        assert "geldig" in (job.get("error") or ""), f"torrent module does not work: {job.get('error')}"
        print("  ok: libtorrent aanwezig")
        call("/api/quit", {})
        proc.wait(timeout=30)
        print("exited with code", proc.returncode)
    finally:
        if proc.poll() is None:
            proc.kill()


if __name__ == "__main__":
    main()
