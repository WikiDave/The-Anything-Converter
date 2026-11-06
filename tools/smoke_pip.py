"""Smoke test for a pip / pipx install, on any OS (used by CI on Linux x64/ARM, macOS, Windows, FreeBSD, Alpine).

Run with the Python of the install:  python tools/smoke_pip.py [--full]
Makes test files, converts them with the installed 'anything-converter-tui', and starts the web interface.
Media conversions are only tested when ffmpeg is on the PATH.
"""
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

FULL = "--full" in sys.argv
exe = shutil.which("anything-converter-tui")
if not exe:
    sys.exit("anything-converter-tui is not on the PATH")
work = Path(tempfile.mkdtemp(prefix="ac-smoke-"))
out = work / "out"
out.mkdir()

from converter import samples  # noqa: E402  (from the installed package)

cases = [("png", "webp"), ("png", "pdf"), ("csv", "json"), ("json", "yaml"), ("docx", "txt"), ("zip", "tar")]
if shutil.which("ffmpeg"):
    cases += [("wav", "mp3"), ("mp4", "mov")]
else:
    print("(no ffmpeg on the PATH: skipping video/audio)")
if FULL:
    cases += [("pdf", "png"), ("docx", "pdf"), ("zip", "7z")]

fails = []
for src_ext, to in cases:
    src = samples.make_sample(src_ext, work)
    if not src:
        fails.append(f"no sample for .{src_ext}")
        continue
    r = subprocess.run([exe, "convert", str(src), "--to", to, "--out", str(out)], capture_output=True, text=True)
    made = list(out.glob(f"{src.stem}*.{to}"))
    ok = r.returncode == 0 and made
    print(f"{'ok  ' if ok else 'FAIL'} .{src_ext} -> .{to}")
    if not ok:
        fails.append(f".{src_ext} -> .{to}: {r.stdout[-400:]} {r.stderr[-400:]}")
    for m in made:
        m.unlink()

for args in (["--version"], ["presets"], ["drives", "list"]):
    r = subprocess.run([exe, *args], capture_output=True, text=True)
    print(f"{'ok  ' if r.returncode == 0 else 'FAIL'} {' '.join(args)}")
    if r.returncode != 0 and args[0] != "drives":  # drives may lack tools in a VM; must not crash though
        fails.append(f"{args}: {r.stdout[-300:]} {r.stderr[-300:]}")
    if "Traceback" in r.stderr:
        fails.append(f"{args} crashed: {r.stderr[-600:]}")

# the web interface
port = "8765"
srv = subprocess.Popen([exe, "serve", "--port", port], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    for path in ("/api/ping", "/", "/static/app.js", "/web/"):
        body = b""
        for _ in range(30):
            try:
                body = urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5).read()
                break
            except OSError:
                time.sleep(1)
        print(f"{'ok  ' if body else 'FAIL'} GET {path} ({len(body)} bytes)")
        if not body:
            fails.append(f"GET {path}")
finally:
    srv.terminate()

shutil.rmtree(work, ignore_errors=True)
if fails:
    print("\nFAILED:\n  " + "\n  ".join(fails))
    sys.exit(1)
print("\nall good")
